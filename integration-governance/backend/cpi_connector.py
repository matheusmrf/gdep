"""
CPI Connector - Integração com SAP CPI via API

Este módulo fornece funcionalidade para conectar ao SAP CPI e extrair informações
sobre integrações, endpoints, artefatos e métricas de desempenho.
"""

import logging
import base64
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urljoin, urlparse

import requests

logger = logging.getLogger(__name__)


def calculate_metrics(messages: List[Dict]) -> Dict:
    if not messages:
        return {
            "total_messages": 0,
            "failed": 0,
            "error_rate": 0.0,
            "avg_time": 0.0,
            "has_data": False,
            "artifact_id": None,
            "sender": None,
            "receiver": None,
            "artifact_name": None,
            "integration_flow_name": None,
        }

    total_messages = len(messages)
    failed = sum(1 for message in messages if message.get("status") in {"FAILED", "RETRY"})
    processing_times = [
        float(message.get("processing_time"))
        for message in messages
        if message.get("processing_time") not in (None, "")
    ]

    avg_time = sum(processing_times) / len(processing_times) if processing_times else 0.0

    # Pick the most common non-null sender/receiver/name
    from collections import Counter

    def most_common(values):
        vals = [v for v in values if v]
        return Counter(vals).most_common(1)[0][0] if vals else None

    return {
        "total_messages": total_messages,
        "failed": failed,
        "error_rate": failed / total_messages if total_messages else 0.0,
        "avg_time": avg_time,
        "has_data": True,
        "artifact_id": most_common(m.get("artifact_id") for m in messages),
        "sender": most_common(m.get("sender") for m in messages),
        "receiver": most_common(m.get("receiver") for m in messages),
        "artifact_name": most_common(m.get("artifact_name") for m in messages),
        "integration_flow_name": most_common(m.get("integration_flow_name") for m in messages),
    }


def parse_odata_datetime(value: Optional[str]) -> Optional[int]:
    """Parse /Date(ms)/ or ISO8601 datetime string to epoch milliseconds."""
    if not value:
        return None
    # OData JSON format: /Date(1234567890)/
    if value.startswith("/Date("):
        try:
            return int(value[6:].split(")")[0])
        except ValueError:
            return None
    # ISO8601 format: 2026-03-02T17:40:00.406
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except (ValueError, TypeError):
        return None


class CPIConnector:
    """Connector para SAP CPI Cloud Integration"""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        tenant_id: str,
        verify_ssl: bool = True,
    ):
        """
        Inicializa o conector CPI.

        Args:
            host: URL do host CPI (ex: l400231-tmn.hci.br1.hana.ondemand.com)
            username: Usuário para autenticação
            password: Senha para autenticação
            tenant_id: ID do tenant CPI
            verify_ssl: Verificar certificado SSL (padrão: True)
        """
        self.host = host
        self.username = username
        self.password = password
        self.tenant_id = tenant_id
        self.verify_ssl = verify_ssl
        self.base_url = f"https://{host}"
        self._session = None

    @property
    def session(self) -> requests.Session:
        """Lazy initialization of requests session with basic auth"""
        if self._session is None:
            self._session = requests.Session()
            auth_string = base64.b64encode(
                f"{self.username}:{self.password}".encode()
            ).decode()
            self._session.headers.update(
                {
                    "Authorization": f"Basic {auth_string}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }
            )
        return self._session

    def get_integration_artifacts(self) -> List[Dict]:
        """
        Obtém lista de todos os integration flows (iFlows) do CPI.

        Returns:
            Lista de artefatos de integração com metadata
        """
        try:
            # Endpoint que obtém lista de participants do CPI
            url = urljoin(
                self.base_url,
                f"/itspaces/Operations/com.sap.it.op.srv.commands.dashboard.ParticipantListCommand?tenantId={self.tenant_id}",
            )

            response = self.session.get(url, verify=self.verify_ssl, timeout=30)
            response.raise_for_status()

            data = response.json()
            artifacts = []

            participant_info = data.get("participantInformation", [])
            if isinstance(participant_info, dict):
                participant_info = [participant_info]

            seen_keys = set()

            for participant in participant_info:
                nodes = participant.get("nodes", [])
                if isinstance(nodes, dict):
                    nodes = [nodes]

                for node_info in nodes:
                    node = node_info.get("node", {})
                    if not isinstance(node, dict):
                        continue

                    components = node.get("components", [])
                    if isinstance(components, dict):
                        components = [components]

                    for component in components:
                        if component.get("type") != "INTEGRATION_FLOW":
                            continue

                        symbolic_name = None
                        for tag in component.get("tags", []):
                            if tag.get("name") == "Bundle-SymbolicName":
                                symbolic_name = tag.get("value")
                                break

                        artifact = {
                            "id": component.get("artifactId"),
                            "name": component.get("name"),
                            "symbolicName": symbolic_name or component.get("name"),
                            "type": component.get("type"),
                            "version": component.get("version"),
                            "state": component.get("state"),
                            "deployed": component.get("state") == "STARTED",
                        }
                        artifact_key = artifact["id"] or artifact["name"]
                        if artifact_key in seen_keys:
                            continue
                        seen_keys.add(artifact_key)
                        artifacts.append(artifact)

            logger.info(f"Found {len(artifacts)} integration artifacts in CPI")
            return artifacts

        except Exception as e:
            logger.error(f"Error fetching integration artifacts from CPI: {str(e)}")
            raise

    def get_integration_endpoints(self, artifact_id: str) -> List[Dict]:
        """
        Obtém endpoints de um integration flow específico.

        Args:
            artifact_id: ID do artifact/iFlow

        Returns:
            Lista de endpoints com suas URLs
        """
        try:
            url = urljoin(
                self.base_url,
                f"/itspaces/Operations/com.sap.it.op.tmn.commands.dashboard.webui.IntegrationComponentDetailCommand?artifactId={artifact_id}",
            )

            response = self.session.get(url, verify=self.verify_ssl, timeout=30)
            response.raise_for_status()

            data = response.json()
            endpoints = []

            if "endpointInformation" in data:
                for endpoint_info in data["endpointInformation"]:
                    if "endpointInstances" in endpoint_info:
                        for instance in endpoint_info["endpointInstances"]:
                            endpoints.append(
                                {
                                    "url": instance.get("endpointUrl"),
                                    "category": instance.get("endpointCategory"),
                                    "protocol": instance.get("protocol"),
                                }
                            )

            return endpoints

        except Exception as e:
            logger.error(f"Error fetching endpoints for artifact {artifact_id}: {str(e)}")
            return []

    def get_recent_message_processing_logs(self, limit: int = 5000, days: int = 30) -> List[Dict]:
        try:
            url = urljoin(self.base_url, "/api/v1/MessageProcessingLogs")
            messages = []
            since = datetime.now(timezone.utc) - timedelta(days=days)
            since_str = since.strftime("%Y-%m-%dT%H:%M:%S")
            # Do NOT set $top — CPI returns 1000/page with $skiptoken pagination.
            # Controlling total via len(messages) >= limit in the loop.
            params = {
                "$format": "json",
                "$filter": f"Status ne 'PROCESSING' and LogEnd ge datetime'{since_str}'",
                "$orderby": "LogEnd desc",
            }

            while True:
                response = self.session.get(url, params=params, verify=self.verify_ssl, timeout=30)
                response.raise_for_status()

                data = response.json()
                results = data.get("d", {}).get("results", [])
                for msg in results:
                    artifact = msg.get("IntegrationArtifact") or {}
                    artifact_id = artifact.get("Id")
                    artifact_name = artifact.get("Name")
                    integration_flow_name = msg.get("IntegrationFlowName")
                    if not any([artifact_id, artifact_name, integration_flow_name]):
                        continue

                    start = parse_odata_datetime(msg.get("LogStart"))
                    end = parse_odata_datetime(msg.get("LogEnd"))
                    processing_time = float(end - start) if start and end and end >= start else None
                    messages.append(
                        {
                            "id": msg.get("MessageGuid"),
                            "artifact_id": artifact_id,
                            "artifact_name": artifact_name,
                            "integration_flow_name": integration_flow_name,
                            "timestamp": msg.get("LogEnd") or msg.get("LogStart"),
                            "status": msg.get("Status"),
                            "error": msg.get("Status") == "FAILED",
                            "processing_time": processing_time,
                            "sender": msg.get("Sender") or None,
                            "receiver": msg.get("Receiver") or None,
                        }
                    )
                    if len(messages) >= limit:
                        return messages[:limit]

                next_link = data.get("d", {}).get("__next")
                if not next_link:
                    break

                parsed_next = urlparse(next_link)
                params = {key: values[-1] for key, values in parse_qs(parsed_next.query).items()}

            return messages

        except Exception as e:
            logger.error(f"Error fetching recent message logs from CPI: {str(e)}")
            return []

    def get_messages_for_artifact(self, artifact_id: str, limit: int = 100) -> List[Dict]:
        """Targeted MPL fetch for a specific artifact (fallback for low-frequency flows)."""
        try:
            url = urljoin(self.base_url, "/api/v1/MessageProcessingLogs")
            params = {
                "$top": limit,
                "$format": "json",
                "$filter": f"IntegrationArtifact/Id eq '{artifact_id}' and Status ne 'PROCESSING'",
                "$orderby": "LogEnd desc",
            }
            response = self.session.get(url, params=params, verify=self.verify_ssl, timeout=30)
            response.raise_for_status()
            messages = []
            for msg in response.json().get("d", {}).get("results", []):
                artifact = msg.get("IntegrationArtifact") or {}
                start = parse_odata_datetime(msg.get("LogStart"))
                end = parse_odata_datetime(msg.get("LogEnd"))
                processing_time = float(end - start) if start and end and end >= start else None
                messages.append(
                    {
                        "id": msg.get("MessageGuid"),
                        "artifact_id": artifact.get("Id"),
                        "artifact_name": artifact.get("Name"),
                        "integration_flow_name": msg.get("IntegrationFlowName"),
                        "timestamp": msg.get("LogEnd") or msg.get("LogStart"),
                        "status": msg.get("Status"),
                        "error": msg.get("Status") == "FAILED",
                        "processing_time": processing_time,
                        "sender": msg.get("Sender") or None,
                        "receiver": msg.get("Receiver") or None,
                    }
                )
            return messages
        except Exception as e:
            logger.error(f"Error fetching messages for artifact {artifact_id}: {str(e)}")
            return []

    def get_metrics_by_artifact(self, limit: int = 500) -> Dict[str, Dict]:
        """
        Returns metrics dict keyed by CANONICAL artifact_id (symbolic name from MPL).
        Each canonical entry also includes alias keys (artifact_name, integration_flow_name)
        so lookup by any identifier works.
        """
        # Group by canonical key: artifact_id first, then flow_name, then name
        canonical_groups: Dict[str, list] = {}
        key_to_canonical: Dict[str, str] = {}

        for message in self.get_recent_message_processing_logs(limit=limit):
            artifact_id = message.get("artifact_id")
            flow_name = message.get("integration_flow_name")
            art_name = message.get("artifact_name")

            canonical = artifact_id or flow_name or art_name
            if not canonical:
                continue

            if canonical not in canonical_groups:
                canonical_groups[canonical] = []
            canonical_groups[canonical].append(message)

            # Register aliases → canonical
            for alias in (artifact_id, flow_name, art_name):
                if alias and alias not in key_to_canonical:
                    key_to_canonical[alias] = canonical

        # Compute metrics per canonical key
        canonical_metrics = {
            canonical: calculate_metrics(msgs)
            for canonical, msgs in canonical_groups.items()
        }

        # Build final dict: canonical + all aliases → same metrics object
        result: Dict[str, Dict] = {}
        for alias, canonical in key_to_canonical.items():
            result[alias] = canonical_metrics[canonical]

        return result

    def health_check(self) -> bool:
        """
        Verifica se o CPI está acessível e autenticado.

        Returns:
            True se conexão está ok, False caso contrário
        """
        try:
            url = urljoin(
                self.base_url,
                f"/itspaces/Operations/com.sap.it.op.srv.commands.dashboard.ParticipantListCommand?tenantId={self.tenant_id}",
            )
            response = self.session.get(url, verify=self.verify_ssl, timeout=10)
            is_ok = response.status_code == 200
            if is_ok:
                logger.info(f"CPI health check successful: {response.status_code}")
            else:
                logger.error(f"CPI health check failed: {response.status_code}")
            return is_ok
        except Exception as e:
            logger.error(f"CPI health check failed: {str(e)}")
            return False


def convert_cpi_to_integration(
    artifact: Dict, endpoints: List[Dict]
) -> Dict:
    """
    Converte um artifact do CPI para o modelo de Integration do GDEP.

    Args:
        artifact: Dados do artifact do CPI
        endpoints: Lista de endpoints do artifact

    Returns:
        Dicionário com dados mapeados para Integration
    """
    target_descriptors = []
    for endpoint in endpoints:
        descriptor = endpoint.get("protocol")
        url = endpoint.get("url")
        if not descriptor and url:
            parsed = urlparse(url)
            path_parts = [part for part in parsed.path.split("/") if part]
            if len(path_parts) >= 2:
                descriptor = f"{path_parts[-2]}/{path_parts[-1]}"
            elif path_parts:
                descriptor = path_parts[-1]
            else:
                descriptor = parsed.netloc or url
        if not descriptor:
            descriptor = endpoint.get("category")
        if descriptor:
            target_descriptors.append(str(descriptor))

    unique_descriptors = []
    for descriptor in target_descriptors:
        if descriptor not in unique_descriptors:
            unique_descriptors.append(descriptor)

    endpoint_urls = []
    for endpoint in endpoints:
        endpoint_url = endpoint.get("url")
        if endpoint_url and endpoint_url not in endpoint_urls:
            endpoint_urls.append(endpoint_url)

    return {
        "name": artifact.get("name", artifact.get("symbolicName", "Unknown")),
        "platform": "CPI",
        "source_system": "SAP CPI",
        "target_system": ", ".join(unique_descriptors[:3]) or "Unknown",
        "monthly_volume": 0,  # Will be updated from message logs
        "error_count": 0,  # Will be updated from message logs
        "error_rate": 0.0,
        "avg_processing_time": 0.0,
        "business_weight": 5,  # Default medium priority
        "score": 50.0,
        "criticality": "Média",
        "external_id": artifact.get("id"),
        "external_source": "CPI",
        "cpi_symbolic_name": artifact.get("symbolicName"),
        "cpi_artifact_type": artifact.get("type"),
        "cpi_version": artifact.get("version"),
        "cpi_state": artifact.get("state"),
        "cpi_deployed": 1 if artifact.get("deployed") else 0,
        "cpi_endpoint_count": len(endpoint_urls),
        "cpi_endpoint_urls": ", ".join(endpoint_urls) if endpoint_urls else None,
        "cpi_sender": None,
        "cpi_receiver": None,
        "cpi_integration_flow_name": None,
        "cpi_artifact_name": artifact.get("name"),
    }

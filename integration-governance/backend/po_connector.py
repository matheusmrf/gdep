"""SAP PO connector for directory/runtime data collection.

This module intentionally supports multiple payload shapes (XML and JSON)
because SAP PO deployments vary by patch and enabled services.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
import json
import logging
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

import requests


logger = logging.getLogger(__name__)


SUCCESS_STATUSES = {"SUCCESS"}
ERROR_STATUSES = {"ERROR", "FAILED", "SYSTEM_ERROR", "CANCELLED"}

LEGACY_PO_HOSTS = {
    "xq3abpas.arcelormittal.com.br:50000",
    "xq3abpas.arcelormittal.com.br",
}
DEFAULT_PO_HOST = "https://integrationqas.arcelormittal.com.br"


def normalize_po_host(host: str) -> str:
    host = (host or "").strip()
    host_no_scheme = host.replace("https://", "").replace("http://", "").rstrip("/")
    if host_no_scheme in LEGACY_PO_HOSTS:
        return DEFAULT_PO_HOST
    if host.startswith("http://") or host.startswith("https://"):
        return host.rstrip("/")
    return f"https://{host.rstrip('/')}"


def _safe_int(value: Optional[str], default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(str(value).strip()))
    except Exception:
        return default


def _safe_float(value: Optional[str], default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(str(value).strip())
    except Exception:
        return default


def _tag_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _find_text_any(elem: ET.Element, names: List[str]) -> Optional[str]:
    name_set = {n.lower() for n in names}
    for node in elem.iter():
        if _tag_name(node.tag).lower() in name_set:
            text = (node.text or "").strip()
            if text:
                return text
    return None


class SAPPOConnector:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        verify_ssl: bool = True,
        timeout: int = 30,
    ):
        self.base_url = normalize_po_host(host)
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.timeout = timeout

        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update(
            {
                "Accept": "application/json, application/xml, text/xml, */*",
                "User-Agent": "GDEP-SAP-PO-Connector/1.0",
            }
        )

    def health_check(self) -> bool:
        urls = [
            f"{self.base_url}/AdapterFramework/MessageMonitoring",
            f"{self.base_url}/AdapterFramework",
        ]
        for url in urls:
            try:
                resp = self.session.get(url, verify=self.verify_ssl, timeout=10)
                if resp.status_code in (200, 401, 403):
                    return resp.status_code == 200
            except Exception:
                continue
        return False

    def get_runtime_messages(self, days: int = 1, limit: int = 5000) -> List[Dict]:
        """Fetch runtime message monitoring data from Adapter Engine APIs.

        Different PO landscapes expose different formats; this method parses both
        JSON and XML responses and normalizes records.
        """
        since = datetime.utcnow() - timedelta(days=days)
        since_iso = since.strftime("%Y-%m-%dT%H:%M:%S")
        urls = [
            f"{self.base_url}/AdapterFramework/MessageMonitoring?from={since_iso}&maxMessages={limit}",
            f"{self.base_url}/AdapterFramework/MessageMonitoring?maxMessages={limit}",
        ]

        for url in urls:
            try:
                response = self.session.get(url, verify=self.verify_ssl, timeout=self.timeout)
                if response.status_code != 200:
                    continue
                body = response.text.strip()
                if not body:
                    continue

                if body.startswith("{") or body.startswith("["):
                    return self._parse_json_messages(body)
                return self._parse_xml_messages(body)
            except Exception as exc:
                logger.warning(f"SAP PO runtime request failed ({url}): {exc}")
                continue
        return []

    def get_directory_integrations(self) -> List[Dict]:
        """Best-effort fetch from Directory API (IntegratedConfigurationIn/query)."""
        soap_envelope = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<soapenv:Envelope xmlns:soapenv=\"http://schemas.xmlsoap.org/soap/envelope/\">
  <soapenv:Body>
    <query xmlns=\"urn:com.sap.aii.ibdir.server.api.types\">
      <queryCondition/>
      <readContextCode>CONFIGURED_OBJECTS</readContextCode>
    </query>
  </soapenv:Body>
</soapenv:Envelope>"""

        candidates = [
            f"{self.base_url}/rep/support/SimpleQuery",
            f"{self.base_url}/rep/support/IntegratedConfigurationIn",
        ]
        headers = {"Content-Type": "text/xml; charset=utf-8"}

        for url in candidates:
            try:
                response = self.session.post(
                    url,
                    data=soap_envelope.encode("utf-8"),
                    headers=headers,
                    verify=self.verify_ssl,
                    timeout=self.timeout,
                )
                if response.status_code != 200:
                    continue
                integrations = self._parse_directory_xml(response.text)
                if integrations:
                    return integrations
            except Exception as exc:
                logger.warning(f"SAP PO directory query failed ({url}): {exc}")
                continue
        return []

    def aggregate_metrics(self, messages: List[Dict]) -> Dict[str, Dict]:
        grouped: Dict[str, List[Dict]] = defaultdict(list)
        for msg in messages:
            key = msg.get("integration_key")
            if not key:
                continue
            grouped[key].append(msg)

        aggregated: Dict[str, Dict] = {}
        for key, items in grouped.items():
            total = len(items)
            success = sum(1 for m in items if (m.get("status") or "").upper() in SUCCESS_STATUSES)
            errors = sum(1 for m in items if (m.get("status") or "").upper() in ERROR_STATUSES)
            retries = sum(1 for m in items if (m.get("status") or "").upper() == "RETRY")
            waiting = sum(1 for m in items if (m.get("status") or "").upper() == "WAITING")
            scheduled = sum(1 for m in items if (m.get("status") or "").upper() == "SCHEDULED")

            times = [m.get("processing_time") or 0.0 for m in items if (m.get("processing_time") or 0.0) > 0]
            avg_time = sum(times) / len(times) if times else 0.0
            first = items[0]
            aggregated[key] = {
                "integration_key": key,
                "name": first.get("interface") or key,
                "sender": first.get("sender") or "SAP PO",
                "receiver": first.get("receiver") or "Unknown",
                "total_messages": total,
                "success": success,
                "failed": errors,
                "retry": retries,
                "waiting": waiting,
                "scheduled": scheduled,
                "error_rate": (errors / total) if total else 0.0,
                "avg_time": avg_time,
                "has_data": total > 0,
            }
        return aggregated

    def _parse_json_messages(self, body: str) -> List[Dict]:
        parsed = json.loads(body)
        records: List[Dict]
        if isinstance(parsed, list):
            records = parsed
        elif isinstance(parsed, dict):
            records = parsed.get("messages") or parsed.get("Message") or parsed.get("items") or []
            if isinstance(records, dict):
                records = [records]
        else:
            records = []

        normalized: List[Dict] = []
        for r in records:
            if not isinstance(r, dict):
                continue
            interface = (
                r.get("interface")
                or r.get("Interface")
                or r.get("interfaceName")
                or r.get("senderInterface")
            )
            sender = r.get("sender") or r.get("Sender") or r.get("senderComponent")
            receiver = r.get("receiver") or r.get("Receiver") or r.get("receiverComponent")
            status = r.get("status") or r.get("Status")
            processing = r.get("processingTime") or r.get("ProcessingTime")
            if not interface:
                continue
            key = f"{interface}|{sender or 'UNKNOWN'}|{receiver or 'UNKNOWN'}"
            normalized.append(
                {
                    "integration_key": key,
                    "interface": interface,
                    "sender": sender,
                    "receiver": receiver,
                    "status": str(status or "UNKNOWN").upper(),
                    "processing_time": _safe_float(processing),
                }
            )
        return normalized

    def _parse_xml_messages(self, body: str) -> List[Dict]:
        root = ET.fromstring(body)
        normalized: List[Dict] = []

        # Accept different tag names across PO releases
        message_nodes = [
            node
            for node in root.iter()
            if _tag_name(node.tag).lower() in {"message", "messagemonitoringrecord", "item"}
        ]

        for node in message_nodes:
            interface = _find_text_any(node, ["Interface", "interfaceName", "SenderInterface", "senderInterface"])
            sender = _find_text_any(node, ["SenderComponent", "senderComponent", "Sender"])
            receiver = _find_text_any(node, ["ReceiverComponent", "receiverComponent", "Receiver"])
            status = _find_text_any(node, ["Status", "messageStatus"])
            processing = _find_text_any(node, ["ProcessingTime", "processingTime", "durationMs"])
            if not interface:
                continue
            key = f"{interface}|{sender or 'UNKNOWN'}|{receiver or 'UNKNOWN'}"
            normalized.append(
                {
                    "integration_key": key,
                    "interface": interface,
                    "sender": sender,
                    "receiver": receiver,
                    "status": str(status or "UNKNOWN").upper(),
                    "processing_time": _safe_float(processing),
                }
            )

        return normalized

    def _parse_directory_xml(self, body: str) -> List[Dict]:
        root = ET.fromstring(body)
        candidates = [
            node
            for node in root.iter()
            if _tag_name(node.tag).lower() in {"integratedconfiguration", "item", "configuration"}
        ]

        integrations: List[Dict] = []
        seen = set()
        for node in candidates:
            interface = _find_text_any(node, ["SenderInterface", "senderInterface", "Interface", "interfaceName"])
            sender = _find_text_any(node, ["SenderComponent", "senderComponent"])
            receiver = _find_text_any(node, ["ReceiverComponent", "receiverComponent"])
            if not interface:
                continue
            key = f"{interface}|{sender or 'UNKNOWN'}|{receiver or 'UNKNOWN'}"
            if key in seen:
                continue
            seen.add(key)
            integrations.append(
                {
                    "integration_key": key,
                    "name": interface,
                    "sender": sender or "SAP PO",
                    "receiver": receiver or "Unknown",
                }
            )
        return integrations

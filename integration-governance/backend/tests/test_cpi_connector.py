"""
Testes para CPI Connector

Execução:
    pytest backend/tests/test_cpi_connector.py
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from backend.cpi_connector import CPIConnector, calculate_metrics, convert_cpi_to_integration


class TestCPIConnector:
    """Testes para o conector CPI"""

    @pytest.fixture
    def connector(self):
        """Fixture para criar um conector CPI"""
        return CPIConnector(
            host="test-tmn.hci.br1.hana.ondemand.com",
            username="test_user",
            password="test_pass",
            tenant_id="test_tenant",
        )

    def test_connector_initialization(self, connector):
        """Testa inicialização do conector"""
        assert connector.host == "test-tmn.hci.br1.hana.ondemand.com"
        assert connector.username == "test_user"
        assert connector.tenant_id == "test_tenant"
        assert connector.base_url == "https://test-tmn.hci.br1.hana.ondemand.com"

    def test_health_check_success(self, connector):
        """Testa health check com sucesso"""
        with patch("requests.Session.get") as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            result = connector.health_check()
            assert result is True

    def test_health_check_failure(self, connector):
        """Testa health check com falha"""
        with patch("requests.Session.get") as mock_get:
            mock_get.side_effect = Exception("Connection error")

            result = connector.health_check()
            assert result is False

    def test_session_creation(self, connector):
        """Testa criação da sessão com autenticação"""
        session = connector.session
        assert session is not None
        assert "Authorization" in session.headers
        assert session.headers["Authorization"].startswith("Basic ")

    def test_get_integration_artifacts_parses_participant_list(self, connector):
        payload = {
            "participantInformation": [
                {
                    "id": "tenant-1",
                    "name": "tenant",
                    "nodes": [
                        {
                            "id": "node-1",
                            "name": "worker",
                            "node": {
                                "components": [
                                    {
                                        "name": "Flow A",
                                        "artifactId": "artifact-a",
                                        "type": "INTEGRATION_FLOW",
                                        "version": "1.0.0",
                                        "state": "STARTED",
                                        "tags": [
                                            {
                                                "name": "Bundle-SymbolicName",
                                                "value": "flow_a",
                                            }
                                        ],
                                    },
                                    {
                                        "name": "Security",
                                        "artifactId": "service-1",
                                        "type": "ESSENTIAL_SERVICE",
                                        "version": "1.0.0",
                                        "state": "STARTED",
                                        "tags": [],
                                    },
                                ]
                            },
                        }
                    ],
                }
            ]
        }

        with patch("requests.Session.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = payload
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response

            artifacts = connector.get_integration_artifacts()

        assert len(artifacts) == 1
        assert artifacts[0]["id"] == "artifact-a"
        assert artifacts[0]["name"] == "Flow A"
        assert artifacts[0]["symbolicName"] == "flow_a"
        assert artifacts[0]["deployed"] is True

    def test_get_recent_message_processing_logs_ignores_processing_and_paginates(self, connector):
        first_page = {
            "d": {
                "results": [
                    {
                        "MessageGuid": "m-1",
                        "Status": "PROCESSING",
                        "LogStart": None,
                        "LogEnd": None,
                        "IntegrationFlowName": None,
                        "IntegrationArtifact": {"Id": None, "Name": None},
                    },
                    {
                        "MessageGuid": "m-2",
                        "Status": "COMPLETED",
                        "LogStart": "/Date(1000)/",
                        "LogEnd": "/Date(2000)/",
                        "IntegrationFlowName": "flow_a",
                        "IntegrationArtifact": {"Id": "flow_a", "Name": "Flow A"},
                    },
                ],
                "__next": "MessageProcessingLogs?%24top=5000&$skiptoken=1000&$top=4000",
            }
        }
        second_page = {
            "d": {
                "results": [
                    {
                        "MessageGuid": "m-3",
                        "Status": "FAILED",
                        "LogStart": "/Date(3000)/",
                        "LogEnd": "/Date(5000)/",
                        "IntegrationFlowName": "flow_b",
                        "IntegrationArtifact": {"Id": "flow_b", "Name": "Flow B"},
                    }
                ]
            }
        }

        with patch("requests.Session.get") as mock_get:
            mock_response_1 = Mock()
            mock_response_1.json.return_value = first_page
            mock_response_1.raise_for_status.return_value = None
            mock_response_2 = Mock()
            mock_response_2.json.return_value = second_page
            mock_response_2.raise_for_status.return_value = None
            mock_get.side_effect = [mock_response_1, mock_response_2]

            logs = connector.get_recent_message_processing_logs(limit=5000)

        assert len(logs) == 2
        assert logs[0]["artifact_id"] == "flow_a"
        assert logs[0]["processing_time"] == 1000.0  # ms: /Date(2000)/ - /Date(1000)/ = 1000 ms
        assert logs[1]["artifact_name"] == "Flow B"
        assert logs[1]["status"] == "FAILED"


class TestConvertCPIToIntegration:
    """Testes para conversão de artifact CPI para Integration GDEP"""

    def test_convert_artifact_basic(self):
        """Testa conversão básica de artifact"""
        artifact = {
            "id": "12345",
            "name": "Test Integration Flow",
            "symbolicName": "test_iflow",
        }
        endpoints = [
            {"protocol": "HTTP"},
            {"protocol": "SOAP"},
        ]

        result = convert_cpi_to_integration(artifact, endpoints)

        assert result["name"] == "Test Integration Flow"
        assert result["platform"] == "CPI"
        assert result["source_system"] == "SAP CPI"
        assert "HTTP" in result["target_system"]
        assert result["external_id"] == "12345"
        assert result["external_source"] == "CPI"
        assert result["cpi_symbolic_name"] == "test_iflow"
        assert result["cpi_deployed"] == 0

    def test_convert_artifact_no_endpoints(self):
        """Testa conversão com artifact sem endpoints"""
        artifact = {
            "id": "12345",
            "name": "Test Integration",
        }
        endpoints = []

        result = convert_cpi_to_integration(artifact, endpoints)

        assert result["target_system"] == "Unknown"
        assert result["platform"] == "CPI"

    def test_convert_artifact_uses_endpoint_path_when_protocol_missing(self):
        artifact = {
            "id": "12345",
            "name": "Test Integration",
        }
        endpoints = [
            {
                "url": "https://tenant.example.com/http/MES/PM/OrdemManutencao",
                "category": "ENTRY_POINT",
                "protocol": None,
            }
        ]

        result = convert_cpi_to_integration(artifact, endpoints)

        assert result["target_system"] == "PM/OrdemManutencao"
        assert result["cpi_endpoint_count"] == 1
        assert "https://tenant.example.com/http/MES/PM/OrdemManutencao" in result["cpi_endpoint_urls"]


def test_calculate_metrics():
    messages = [
        {"status": "COMPLETED", "processing_time": 100},
        {"status": "FAILED", "processing_time": 200},
        {"status": "RETRY", "processing_time": 300},
    ]

    metrics = calculate_metrics(messages)

    assert metrics["total_messages"] == 3
    assert metrics["failed"] == 2
    assert round(metrics["error_rate"], 2) == 0.67
    assert metrics["avg_time"] == 200
    assert metrics["has_data"] is True

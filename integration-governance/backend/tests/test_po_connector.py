from backend.po_connector import SAPPOConnector, normalize_po_host


def test_normalize_po_host_maps_legacy_host_to_integrationqas():
    assert normalize_po_host("http://xq3abpas.arcelormittal.com.br:50000") == "https://integrationqas.arcelormittal.com.br"
    assert normalize_po_host("xq3abpas.arcelormittal.com.br") == "https://integrationqas.arcelormittal.com.br"


def test_normalize_po_host_adds_https_when_missing_scheme():
    assert normalize_po_host("integrationqas.arcelormittal.com.br") == "https://integrationqas.arcelormittal.com.br"


def test_connector_uses_normalized_base_url():
    connector = SAPPOConnector(
        host="xq3abpas.arcelormittal.com.br:50000",
        username="u",
        password="p",
    )
    assert connector.base_url == "https://integrationqas.arcelormittal.com.br"

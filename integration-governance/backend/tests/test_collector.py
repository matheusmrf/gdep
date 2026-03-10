import importlib


def test_calculate_score_and_classify():
    collector = importlib.import_module("backend.collector")

    score = collector.calculate_score(volume=10000, error_rate=0.02, business_weight=7)
    assert 0 <= score <= 100
    assert collector.classify(85) == "Crítica"
    assert collector.classify(70) == "Alta"
    assert collector.classify(40) == "Média"
    assert collector.classify(10) == "Baixa"


def test_generate_mock_data(app_module):
    collector = importlib.import_module("backend.collector")
    SessionLocal = app_module["database"].SessionLocal
    Integration = app_module["models"].Integration

    collector.generate_mock_data()

    db = SessionLocal()
    count = db.query(Integration).count()
    db.close()

    assert count == 20

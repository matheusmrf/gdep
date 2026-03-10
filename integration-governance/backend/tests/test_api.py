def test_get_integrations_returns_data(client, app_module):
    Integration = app_module["models"].Integration
    SessionLocal = app_module["database"].SessionLocal

    db = SessionLocal()
    db.add_all(
        [
            Integration(
                user_id=1,
                name="Flow_1",
                platform="CPI",
                source_system="ECC",
                target_system="API",
                department="Operações",
                monthly_volume=1000,
                error_count=10,
                error_rate=0.01,
                avg_processing_time=123.4,
                business_weight=5,
                score=42.0,
                criticality="Média",
            ),
            Integration(
                user_id=1,
                name="Flow_2",
                platform="CPI",
                source_system="S4",
                target_system="API",
                department="Operações",
                monthly_volume=2000,
                error_count=20,
                error_rate=0.01,
                avg_processing_time=200.0,
                business_weight=8,
                score=75.0,
                criticality="Alta",
            ),
        ]
    )
    db.commit()
    db.close()

    response = client.get("/integrations")

    assert response.status_code == 200
    payload = response.json()
    data = payload["items"]
    assert isinstance(data, list)
    assert payload["total"] == 2
    assert len(data) == 2
    assert {item["name"] for item in data} == {"Flow_1", "Flow_2"}


def test_get_integrations_supports_filters(client, app_module):
    Integration = app_module["models"].Integration
    SessionLocal = app_module["database"].SessionLocal

    db = SessionLocal()
    db.add_all(
        [
            Integration(
                user_id=1,
                name="Critical_Flow",
                platform="CPI",
                source_system="ECC",
                target_system="API",
                department="Operações",
                monthly_volume=5000,
                error_count=100,
                error_rate=0.02,
                avg_processing_time=100.0,
                business_weight=10,
                score=85.0,
                criticality="Crítica",
            ),
            Integration(
                user_id=1,
                name="Stable_Flow",
                platform="Kafka",
                source_system="MES",
                target_system="Data Lake",
                department="Operações",
                monthly_volume=1500,
                error_count=1,
                error_rate=0.0006,
                avg_processing_time=90.0,
                business_weight=3,
                score=20.0,
                criticality="Baixa",
            ),
        ]
    )
    db.commit()
    db.close()

    response = client.get("/integrations", params={"criticality": "Crítica", "platform": "CPI", "min_score": 80})

    assert response.status_code == 200
    data = response.json()["items"]
    assert len(data) == 1
    assert data[0]["name"] == "Critical_Flow"


def test_summary_endpoint(client, app_module):
    Integration = app_module["models"].Integration
    SessionLocal = app_module["database"].SessionLocal

    db = SessionLocal()
    db.add_all(
        [
            Integration(
                user_id=1,
                name="Flow_1",
                platform="CPI",
                source_system="ECC",
                target_system="API",
                department="Operações",
                monthly_volume=1000,
                error_count=10,
                error_rate=0.01,
                avg_processing_time=123.4,
                business_weight=5,
                score=42.0,
                criticality="Média",
            ),
            Integration(
                user_id=1,
                name="Flow_2",
                platform="CPI",
                source_system="S4",
                target_system="API",
                department="Operações",
                monthly_volume=2000,
                error_count=20,
                error_rate=0.01,
                avg_processing_time=200.0,
                business_weight=8,
                score=75.0,
                criticality="Alta",
            ),
        ]
    )
    db.commit()
    db.close()

    summary_response = client.get("/summary")

    assert summary_response.status_code == 200
    payload = summary_response.json()
    assert payload["total_integrations"] == 2
    assert sum(payload["criticality_distribution"].values()) == 2

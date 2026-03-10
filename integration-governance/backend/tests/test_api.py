def test_get_integrations_returns_data(client, app_module):
    Integration = app_module["models"].Integration
    SessionLocal = app_module["database"].SessionLocal

    db = SessionLocal()
    db.add_all(
        [
            Integration(
                name="Flow_1",
                platform="CPI",
                source_system="ECC",
                target_system="API",
                monthly_volume=1000,
                error_count=10,
                error_rate=0.01,
                avg_processing_time=123.4,
                business_weight=5,
                score=42.0,
                criticality="Média",
            ),
            Integration(
                name="Flow_2",
                platform="CPI",
                source_system="S4",
                target_system="API",
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
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert {item["name"] for item in data} == {"Flow_1", "Flow_2"}

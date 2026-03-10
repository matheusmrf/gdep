import random
from backend.database import SessionLocal
from backend.models import Integration

def calculate_score(volume, error_rate, business_weight):
    score = (volume * 0.0001 * 0.4) + (error_rate * 100 * 0.4) + (business_weight * 0.2)
    return min(score, 100)

def classify(score):
    if score >= 80:
        return "Crítica"
    elif score >= 60:
        return "Alta"
    elif score >= 30:
        return "Média"
    return "Baixa"

def generate_mock_data():
    db = SessionLocal()

    for i in range(20):
        volume = random.randint(1000, 1000000)
        errors = random.randint(0, 5000)
        error_rate = errors / volume if volume > 0 else 0
        business_weight = random.randint(1, 10)

        score = calculate_score(volume, error_rate, business_weight)
        criticality = classify(score)

        integration = Integration(
            name=f"Flow_{i}",
            platform="CPI",
            source_system="ECC",
            target_system="API",
            monthly_volume=volume,
            error_count=errors,
            error_rate=error_rate,
            avg_processing_time=random.uniform(100, 500),
            business_weight=business_weight,
            score=score,
            criticality=criticality
        )

        db.add(integration)

    db.commit()
    db.close()

if __name__ == "__main__":
    generate_mock_data()

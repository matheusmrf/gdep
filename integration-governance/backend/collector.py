def calculate_score(volume, error_rate, business_weight):
    score = (volume * 0.0001 * 0.4) + (error_rate * 100 * 0.4) + (business_weight * 0.2)
    return min(score, 100)


def classify(score):
    if score >= 80:
        return "Crítica"
    if score >= 60:
        return "Alta"
    if score >= 30:
        return "Média"
    return "Baixa"

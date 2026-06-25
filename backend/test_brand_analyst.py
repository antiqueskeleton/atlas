from backend.analysts.brand_analyst import BrandAnalyst


knowledge = {
    "brands": [
        "Firman",
        "Champion",
        "Honda",
        "Westinghouse",
        "Generac",
        "Predator",
        "DuroMax"
    ]
}

evidence = {
    "evidence_id": "test-001",
    "source": "manual_test",
    "text": """
    For home backup, Champion and Westinghouse are often recommended.
    Firman is also a strong value option, especially for dual fuel buyers.
    Honda is usually considered premium and very quiet.
    """
}

analyst = BrandAnalyst(knowledge=knowledge)
result = analyst.analyze(evidence)

print(result)
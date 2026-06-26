from dataclasses import dataclass


@dataclass
class InvestigationRequest:
    question: str

    intent: str = "general"

    target_brand: str | None = None

    target_feature: str | None = None

    competitor: str | None = None
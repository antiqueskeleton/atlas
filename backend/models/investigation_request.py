from dataclasses import dataclass, field

from backend.models.comp_shop_request import CompShopRequest


@dataclass
class InvestigationRequest:
    question: str

    intent: str = "general"

    target_brand: str | None = None

    target_feature: str | None = None

    competitor: str | None = None

    comp_shop: CompShopRequest | None = None
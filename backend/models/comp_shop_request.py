from dataclasses import dataclass, field


@dataclass
class CompShopRequest:
    target_product: str | None = None
    competitor_products: list[str] = field(default_factory=list)
    customer: str | None = None
    category: str | None = None
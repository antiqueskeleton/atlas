from dataclasses import dataclass
from datetime import datetime


@dataclass
class VisibilityResponse:
    run_id: str
    provider: str
    model: str
    prompt: str
    response: str
    collected_at: datetime
    family_name: str = ""
    # Source URLs the provider reported grounding this answer on (#96) —
    # None for providers that don't expose citations.
    citations: list | None = None
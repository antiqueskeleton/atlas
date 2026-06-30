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
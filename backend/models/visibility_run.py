from dataclasses import dataclass
from datetime import datetime


@dataclass
class VisibilityRun:
    run_id: str
    provider: str
    model: str
    prompt_set: str

    started_at: datetime

    completed_at: datetime | None = None

    status: str = "Running"

    response_count: int = 0

    duration_seconds: float = 0.0
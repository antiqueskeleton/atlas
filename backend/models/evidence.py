from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


@dataclass
class Evidence:
    """
    A raw observation collected by Atlas.

    Evidence is never modified.
    Analysts read Evidence and produce Findings.
    """

    evidence_id: str
    source: str
    text: str
    prompt: str | None = None
    collected_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
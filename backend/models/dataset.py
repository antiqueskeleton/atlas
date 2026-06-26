from dataclasses import dataclass, field
from datetime import datetime

from backend.models.evidence import Evidence


@dataclass
class Dataset:
    name: str
    source: str
    imported_at: datetime
    evidence: list[Evidence] = field(default_factory=list)

    @property
    def response_count(self):
        return len(self.evidence)

    @property
    def status(self):
        return "Ready" if self.evidence else "Empty"
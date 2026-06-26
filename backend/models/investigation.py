from dataclasses import dataclass, field
from typing import List

from backend.models.insight import Insight
from backend.models.relationship import Relationship


@dataclass
class Investigation:

    question: str

    insights: List[Insight] = field(default_factory=list)

    relationships: List[Relationship] = field(default_factory=list)

    recommendations: List[str] = field(default_factory=list)
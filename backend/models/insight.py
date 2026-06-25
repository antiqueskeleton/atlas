from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class Insight:
    """
    A business conclusion generated from Findings.
    """

    title: str
    description: str
    confidence: float
    insight_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)
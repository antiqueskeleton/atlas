from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class Relationship:
    """
    Represents a relationship between two findings.
    Example:
        Firman -> Dual Fuel
    """

    source: str
    target: str

    relationship_type: str

    evidence_id: str

    confidence: float

    metadata: Dict[str, Any] = field(default_factory=dict)
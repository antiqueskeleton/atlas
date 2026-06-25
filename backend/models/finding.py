from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class Finding:
    """
    A structured observation produced by an Atlas analyst.
    """

    finding_type: str
    value: str
    confidence: float
    reason: str
    evidence_id: str
    analyst_name: str
    metadata: Dict[str, Any]
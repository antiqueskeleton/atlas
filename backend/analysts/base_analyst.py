from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class AnalysisResult:
    analyst_name: str
    evidence_id: str
    findings: List[Dict[str, Any]]
    confidence: float
    notes: str = ""


class BaseAnalyst(ABC):
    """
    Base class for all Atlas analysts.
    Every analyst receives evidence, analyzes it, and returns structured findings.
    """

    analyst_name = "Base Analyst"

    def __init__(self, knowledge: Dict[str, Any] | None = None):
        self.knowledge = knowledge or {}

    @abstractmethod
    def analyze(self, evidence: Dict[str, Any]) -> AnalysisResult:
        pass

    def validate_evidence(self, evidence: Dict[str, Any]) -> bool:
        return "text" in evidence and bool(evidence["text"])

    def confidence_from_matches(self, matches: int, possible: int) -> float:
        if possible <= 0:
            return 0.0
        return round(min(matches / possible, 1.0), 2)
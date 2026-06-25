from dataclasses import dataclass, field
from typing import Dict, List

from backend.analysts.base_analyst import AnalysisResult


@dataclass
class RunSummary:
    evidence_count: int
    analyst_count: int
    results: List[AnalysisResult]
    finding_counts_by_type: Dict[str, int] = field(default_factory=dict)

    def build(self):
        counts: Dict[str, int] = {}

        for result in self.results:
            for finding in result.findings:
                counts[finding.finding_type] = counts.get(finding.finding_type, 0) + 1

        self.finding_counts_by_type = counts
        return self
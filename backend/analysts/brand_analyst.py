import re
from typing import Any, Dict, List

from backend.analysts.base_analyst import AnalysisResult, BaseAnalyst
from backend.models.evidence import Evidence
from backend.models.finding import Finding


class BrandAnalyst(BaseAnalyst):
    analyst_name = "Brand Analyst"

    def analyze(self, evidence: Evidence) -> AnalysisResult:
        if not self.validate_evidence(evidence):
            return AnalysisResult(
                analyst_name=self.analyst_name,
                evidence_id=evidence.evidence_id,
                findings=[],
                confidence=0.0,
                notes="Invalid evidence. No text found."
            )

        text = evidence.text
        brands = self.knowledge.get("brands", [])
        findings: List[Finding] = []

        for brand in brands:
            pattern = r"\b" + re.escape(brand) + r"\b"
            matches = list(re.finditer(pattern, text, re.IGNORECASE))

            if matches:
                first_position = matches[0].start()

                findings.append(
                    Finding(
                        finding_type="brand",
                        value=brand,
                        confidence=0.95,
                        reason="Exact brand name match",
                        evidence_id=evidence.evidence_id,
                        analyst_name=self.analyst_name,
                        metadata={
                            "mentions": len(matches),
                            "first_position": first_position,
                            "sentiment": "unknown",
                            "source": evidence.source,
                            "prompt": evidence.prompt
                        }
                    )
                )

        findings.sort(
            key=lambda item: item.metadata["first_position"]
        )

        for index, finding in enumerate(findings, start=1):
            finding.rank = index

        confidence = 0.95 if findings else 0.0

        return AnalysisResult(
            analyst_name=self.analyst_name,
            evidence_id=evidence.evidence_id,
            findings=findings,
            confidence=confidence,
            notes=f"Detected {len(findings)} brand(s)."
        )
import re
from typing import List

from backend.analysts.base_analyst import AnalysisResult, BaseAnalyst
from backend.models.evidence import Evidence
from backend.models.finding import Finding


class FeatureAnalyst(BaseAnalyst):
    analyst_name = "Feature Analyst"

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
        features = self.knowledge.get("features", [])
        findings: List[Finding] = []

        for feature in features:
            pattern = r"\b" + re.escape(feature) + r"\b"
            matches = list(re.finditer(pattern, text, re.IGNORECASE))

            if matches:
                first_position = matches[0].start()

                findings.append(
                    Finding(
                        finding_type="feature",
                        value=feature,
                        confidence=0.90,
                        reason="Exact feature match",
                        evidence_id=evidence.evidence_id,
                        analyst_name=self.analyst_name,
                        metadata={
                            "mentions": len(matches),
                            "first_position": first_position,
                            "source": evidence.source,
                            "prompt": evidence.prompt
                        }
                    )
                )

        findings.sort(key=lambda item: item.metadata["first_position"])

        for index, finding in enumerate(findings, start=1):
            finding.rank = index

        confidence = 0.90 if findings else 0.0

        return AnalysisResult(
            analyst_name=self.analyst_name,
            evidence_id=evidence.evidence_id,
            findings=findings,
            confidence=confidence,
            notes=f"Detected {len(findings)} feature(s)."
        )
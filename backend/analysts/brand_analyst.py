import re
from typing import Any, Dict, List

from backend.analysts.base_analyst import AnalysisResult, BaseAnalyst


class BrandAnalyst(BaseAnalyst):
    analyst_name = "Brand Analyst"

    def analyze(self, evidence: Dict[str, Any]) -> AnalysisResult:
        if not self.validate_evidence(evidence):
            return AnalysisResult(
                analyst_name=self.analyst_name,
                evidence_id=evidence.get("evidence_id", "unknown"),
                findings=[],
                confidence=0.0,
                notes="Invalid evidence. No text found."
            )

        text = evidence["text"]
        brands = self.knowledge.get("brands", [])
        findings: List[Dict[str, Any]] = []

        for brand in brands:
            pattern = r"\b" + re.escape(brand) + r"\b"
            matches = list(re.finditer(pattern, text, re.IGNORECASE))

            if matches:
                first_position = matches[0].start()
                findings.append({
                    "brand": brand,
                    "mentions": len(matches),
                    "first_position": first_position,
                    "sentiment": "unknown",
                    "confidence": 0.95,
                    "reason": "Exact brand name match"
                })

        findings.sort(key=lambda item: item["first_position"])

        for index, finding in enumerate(findings, start=1):
            finding["rank"] = index

        confidence = 0.95 if findings else 0.0

        return AnalysisResult(
            analyst_name=self.analyst_name,
            evidence_id=evidence.get("evidence_id", "unknown"),
            findings=findings,
            confidence=confidence,
            notes=f"Detected {len(findings)} brand(s)."
        )
class EvidenceRanker:
    def rank(self, request, analysis, limit=5):
        if analysis is None:
            return []

        evidence_items = analysis["evidence"]
        target_brand = request.target_brand
        target_feature = request.target_feature

        scored = []

        for evidence in evidence_items:
            score = 0
            text = evidence.text.lower()

            if target_brand and target_brand.lower() in text:
                score += 3

            if target_feature and target_feature.lower() in text:
                score += 2

            if request.competitor and request.competitor.lower() in text:
                score += 1

            scored.append((score, evidence))

        scored.sort(key=lambda item: item[0], reverse=True)

        return [
            evidence for score, evidence in scored[:limit]
            if score > 0
        ]
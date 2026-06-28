class AgentEvidenceSelector:

    def select(self, task_name, analysis, limit=6):
        evidence = analysis.get("evidence", [])

        keyword_map = {
            "Competitive Positioning": [
                "recommend", "brand", "competitor", "visibility", "leader", "market"
            ],
            "Feature Comparison": [
                "feature", "dual fuel", "electric start", "rv ready", "quiet", "inverter"
            ],
            "Customer Sentiment": [
                "love", "hate", "recommend", "complaint", "review", "customer"
            ],
            "Strategic Opportunities": [
                "opportunity", "missing", "improve", "gap", "better"
            ],
        }

        keywords = keyword_map.get(task_name)

        if not keywords:
            return evidence[:limit]

        selected = []

        for item in evidence:
            text = f"{item.prompt} {item.text}".lower()

            if any(word in text for word in keywords):
                selected.append(item)

        return selected[:limit]
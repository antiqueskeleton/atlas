from collections import Counter


class AgentEvidenceSelector:

    KEYWORDS = {
        "Competitive Positioning": [
            "recommend", "brand", "competitor", "market",
            "leader", "visibility", "best", "choice"
        ],

        "Feature Comparison": [
            "feature", "dual fuel", "electric start",
            "rv ready", "quiet", "inverter",
            "remote start", "runtime"
        ],

        "Customer Sentiment": [
            "review", "customer", "love", "hate",
            "complaint", "problem", "recommend",
            "favorite"
        ],

        "Strategic Opportunities": [
            "missing", "opportunity", "gap",
            "improve", "wish", "better",
            "could", "should"
        ]
    }

    def score(self, text, keywords):
        text = text.lower()

        counts = Counter()

        for keyword in keywords:
            counts[keyword] = text.count(keyword)

        return sum(counts.values())

    def select(self, task_name, analysis, limit=8):

        evidence = analysis.get("evidence", [])

        keywords = self.KEYWORDS.get(task_name)

        if not keywords:
            return evidence[:limit]

        ranked = []

        for item in evidence:

            text = (
                item.prompt +
                " " +
                item.text
            )

            score = self.score(
                text,
                keywords
            )

            ranked.append(
                (
                    score,
                    item
                )
            )

        ranked.sort(
            key=lambda x: x[0],
            reverse=True
        )

        return [
            item
            for score, item in ranked
            if score > 0
        ][:limit]
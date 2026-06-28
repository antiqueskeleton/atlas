class AgentEvidenceSelector:

    def select(self, task_name, analysis):
        evidence = analysis.get("evidence", [])

        if task_name == "Competitive Positioning":
            keywords = [
                "recommend",
                "brand",
                "competitor",
                "visibility",
                "leader",
                "market"
            ]

        elif task_name == "Feature Comparison":
            keywords = [
                "feature",
                "dual fuel",
                "electric start",
                "rv ready",
                "quiet",
                "inverter"
            ]

        elif task_name == "Customer Sentiment":
            keywords = [
                "love",
                "hate",
                "recommend",
                "complaint",
                "review",
                "customer"
            ]

        elif task_name == "Strategic Opportunities":
            keywords = [
                "opportunity",
                "missing",
                "improve",
                "gap",
                "better"
            ]

        else:
            return evidence

        selected = []

        for item in evidence:

            text = (
                item.prompt.lower()
                + " "
                + item.response.lower()
            )

            if any(word in text for word in keywords):
                selected.append(item)

        return selected
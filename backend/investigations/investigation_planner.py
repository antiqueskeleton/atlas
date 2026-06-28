from backend.investigations.investigation_plan import InvestigationPlan


class InvestigationPlanner:

    def build(self, question: str) -> InvestigationPlan:
        normalized = question.lower()

        plan = InvestigationPlan(question=question)

        if any(term in normalized for term in [
            "comp shop",
            "compare product",
            "compare products",
            "product a",
            "against competitor",
            "vs",
            "versus",
        ]):
            plan.tasks.extend([
                "Comp Shop",
                "Feature Comparison",
                "Customer Fit",
                "Strategic Opportunities",
            ])
            return plan

        plan.tasks.extend([
            "Competitive Positioning",
            "Feature Comparison",
            "Customer Sentiment",
            "Strategic Opportunities",
        ])

        return plan
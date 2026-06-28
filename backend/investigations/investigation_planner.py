from backend.investigations.investigation_plan import InvestigationPlan


class InvestigationPlanner:

    def build(self, question: str) -> InvestigationPlan:
        normalized = question.lower()

        plan = InvestigationPlan(question=question)

        plan.tasks.append("Competitive Positioning")

        if any(term in normalized for term in [
            "comp shop",
            "compare product",
            "compare products",
            "product a",
            "against competitor",
            "vs",
            "versus",
        ]):
            plan.tasks.append("Comp Shop")

        plan.tasks.extend([
            "Feature Comparison",
            "Customer Sentiment",
            "Strategic Opportunities",
        ])

        return plan
from backend.investigations.investigation_plan import InvestigationPlan


class InvestigationPlanner:

    def build(self, question: str) -> InvestigationPlan:

        plan = InvestigationPlan(question=question)

        plan.tasks.extend([
            "Competitive Positioning",
            "Feature Comparison",
            "Customer Sentiment",
            "Strategic Opportunities",
        ])

        return plan
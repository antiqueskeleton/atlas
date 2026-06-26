from backend.models.investigation import Investigation


class InvestigationEngine:
    def investigate(self, question, insights, relationships):
        return Investigation(
            question=question,
            insights=insights,
            relationships=relationships,
        )
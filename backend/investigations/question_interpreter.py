from backend.models.investigation_request import InvestigationRequest


class QuestionInterpreter:
    def interpret(self, question: str) -> InvestigationRequest:
        normalized = question.lower()

        request = InvestigationRequest(question=question)

        if "why" in normalized:
            request.intent = "explain"

        if "compare" in normalized or "vs" in normalized:
            request.intent = "compare"

        if "firman" in normalized:
            request.target_brand = "Firman"

        if "champion" in normalized:
            request.competitor = "Champion"

        if "honda" in normalized:
            request.competitor = "Honda"

        if "quiet" in normalized:
            request.target_feature = "Quiet Operation"

        if "dual fuel" in normalized:
            request.target_feature = "Dual Fuel"

        return request
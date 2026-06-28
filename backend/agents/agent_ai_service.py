from backend.ai.ai_service import AIService


class AgentAIService:

    def __init__(self, provider_manager):
        self.ai = AIService(provider_manager)

    def ask(self, request, analysis):
        return self.ai.reason(
            request,
            analysis
        )
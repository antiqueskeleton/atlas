from backend.ai.base_provider import AIProvider


class MockAIProvider(AIProvider):
    provider_name = "Mock AI Provider"

    def ask(self, prompt: str, context: str | None = None) -> str:
        return (
            "Mock AI response: Atlas would use a connected AI provider here "
            "to generate reasoning, summaries, recommendations, or structured plans."
        )
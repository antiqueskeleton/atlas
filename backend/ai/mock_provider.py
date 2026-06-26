from backend.ai.base_provider import AIProvider


class MockAIProvider(AIProvider):
    provider_name = "Mock AI Provider"

    def ask(self, prompt: str, context: str | None = None) -> str:
        return (
            "Atlas reasoning preview:\n\n"
            "The question appears to be asking why a target brand is underperforming "
            "against one or more competitors. Based on the current dataset summary, "
            "Atlas would evaluate brand frequency, feature associations, relationship strength, "
            "and supporting evidence before producing a final recommendation.\n\n"
            "This panel is currently powered by the mock AI provider. Later, this same interface "
            "can be connected to OpenAI, Claude, Gemini, Grok, Copilot, or another provider."
        )
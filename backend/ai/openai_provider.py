from backend.ai.base_provider import AIProvider
from backend.models.ai_reasoning import AIReasoning


class OpenAIProvider(AIProvider):
    provider_name = "OpenAI"

    def __init__(self):
        self.api_key = None
        
    def ask(self, prompt: str, context: str | None = None) -> AIReasoning:
        return AIReasoning(
            executive_summary=(
                "OpenAI provider is installed but not yet connected. "
                "API key support and live requests will be added next."
            ),
            confidence="Low",
            risks=[
                "No live OpenAI API request was made.",
                "API key configuration is not implemented yet.",
            ],
            follow_up_questions=[
                "Would you like to configure an OpenAI API key?",
                "Would you like to test the live OpenAI connection?",
            ],
            provider=self.provider_name,
        )
    def set_api_key(self, api_key):
        self.api_key = api_key
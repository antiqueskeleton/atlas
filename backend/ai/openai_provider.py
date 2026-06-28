from backend.ai.base_provider import AIProvider
from backend.models.ai_reasoning import AIReasoning


class OpenAIProvider(AIProvider):
    provider_name = "OpenAI"

    def __init__(self):
        self.api_key = None

    def set_api_key(self, api_key):
        self.api_key = api_key

    def ask(self, prompt: str, context: str | None = None) -> AIReasoning:
        if not self.api_key:
            return AIReasoning(
                executive_summary=(
                    "OpenAI provider is selected, but no API key is configured."
                ),
                confidence="Low",
                risks=[
                    "Atlas cannot make a live OpenAI request without an API key."
                ],
                follow_up_questions=[
                    "Would you like to add an OpenAI API key in Settings?"
                ],
                provider=self.provider_name,
            )

        return AIReasoning(
            executive_summary=(
                "OpenAI provider has an API key configured, but live API requests "
                "are not enabled yet."
            ),
            confidence="Medium",
            opportunities=[
                "Atlas is ready for the next step: enabling live OpenAI requests."
            ],
            risks=[
                "This is still a simulated OpenAI response."
            ],
            follow_up_questions=[
                "Should Atlas make a live OpenAI API request next?"
            ],
            provider=self.provider_name,
        )
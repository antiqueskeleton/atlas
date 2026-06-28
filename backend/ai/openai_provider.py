from backend.ai.base_provider import AIProvider
from backend.ai.openai_client import OpenAIClient
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
                executive_summary="OpenAI provider is selected, but no API key is configured.",
                confidence="Low",
                risks=[
                    "Atlas cannot make a live OpenAI request without an API key."
                ],
                follow_up_questions=[
                    "Would you like to add an OpenAI API key in Settings?"
                ],
                provider=self.provider_name,
            )

        try:
            client = OpenAIClient(self.api_key)
            result = client.generate(prompt)

            return AIReasoning(
                executive_summary=result.response,
                confidence="Medium",
                opportunities=[
                    "Review the live OpenAI response and compare it against Atlas evidence."
                ],
                risks=[
                    "Live AI output should be verified against supporting evidence."
                ],
                follow_up_questions=[
                    "What evidence supports this conclusion?",
                    "How would another AI provider answer this question?",
                ],
                provider=result.provider,
            )

        except Exception as error:
            return AIReasoning(
                executive_summary=f"OpenAI request failed: {error}",
                confidence="Low",
                risks=[
                    "The API key may be invalid, expired, missing billing, or the request may have failed."
                ],
                follow_up_questions=[
                    "Check the OpenAI API key in Settings.",
                    "Try the Mock provider to confirm Atlas is otherwise working.",
                ],
                provider=self.provider_name,
            )
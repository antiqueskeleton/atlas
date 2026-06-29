from backend.ai.base_provider import AIProvider
from backend.ai.openai_client import OpenAIClient
from backend.ai.ai_reasoning_parser import AIReasoningParser
from backend.models.ai_reasoning import AIReasoning


class OpenAIProvider(AIProvider):
    provider_name = "OpenAI"
    model = "gpt-4.1-mini"

    def __init__(self):
        self.api_key = None
        self.model = self.__class__.model
        self.parser = AIReasoningParser()

    def ask(self, prompt: str, context: str | None = None) -> AIReasoning:
        if not self.api_key:
            return AIReasoning(
                executive_summary="OpenAI provider is selected, but no API key is configured.",
                confidence="Low",
                risks=["Atlas cannot make a live OpenAI request without an API key."],
                follow_up_questions=["Would you like to add an OpenAI API key in Settings?"],
                provider=self.provider_name,
            )

        try:
            client = OpenAIClient(self.api_key, model=self.model)
            result = client.generate(prompt)
            return self.parser.parse(text=result.response, provider=result.provider)

        except Exception as error:
            return AIReasoning(
                executive_summary=f"OpenAI request failed ({self.model}): {error}",
                confidence="Low",
                risks=["The API key may be invalid, expired, or missing billing."],
                follow_up_questions=[
                    "Check the OpenAI API key in Settings.",
                    "Models: gpt-4.1, gpt-4.1-mini, gpt-4o, gpt-4o-mini",
                ],
                provider=self.provider_name,
            )

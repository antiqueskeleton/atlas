from backend.ai.base_provider import AIProvider
from backend.ai.ai_reasoning_parser import AIReasoningParser
from backend.models.ai_reasoning import AIReasoning


class MistralProvider(AIProvider):
    provider_name = "Mistral"
    model = "mistral-large-latest"
    _base_url = "https://api.mistral.ai/v1"

    def __init__(self):
        self.api_key = None
        self.parser = AIReasoningParser()

    def set_api_key(self, api_key):
        self.api_key = api_key

    def ask(self, prompt: str, context: str | None = None) -> AIReasoning:
        if not self.api_key:
            return AIReasoning(
                executive_summary="Mistral provider is selected but no API key is configured.",
                confidence="Low",
                risks=["Atlas cannot make a live Mistral request without an API key."],
                follow_up_questions=["Add a Mistral API key in Settings."],
                provider=self.provider_name,
            )

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, base_url=self._base_url)
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            text = response.choices[0].message.content
            return self.parser.parse(text=text, provider=self.provider_name)

        except Exception as error:
            return AIReasoning(
                executive_summary=f"Mistral request failed: {error}",
                confidence="Low",
                risks=["The API key may be invalid or the request timed out."],
                follow_up_questions=["Check the Mistral API key in Settings."],
                provider=self.provider_name,
            )

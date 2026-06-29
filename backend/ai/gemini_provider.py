from backend.ai.base_provider import AIProvider
from backend.ai.ai_reasoning_parser import AIReasoningParser
from backend.models.ai_reasoning import AIReasoning


class GeminiProvider(AIProvider):
    provider_name = "Google Gemini"
    model = "gemini-2.0-flash-001"

    def __init__(self):
        self.api_key = None
        self.model = self.__class__.model
        self.parser = AIReasoningParser()

    def ask(self, prompt: str, context: str | None = None) -> AIReasoning:
        if not self.api_key:
            return AIReasoning(
                executive_summary="Google Gemini provider is selected but no API key is configured.",
                confidence="Low",
                risks=["Atlas cannot make a live Gemini request without an API key."],
                follow_up_questions=["Add a Google Gemini API key in Settings."],
                provider=self.provider_name,
            )

        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            text = response.text or ""
            return self.parser.parse(text=text, provider=self.provider_name)

        except ImportError:
            return AIReasoning(
                executive_summary="The 'google-genai' package is not installed. Run: pip install google-genai",
                confidence="Low",
                risks=["Missing dependency."],
                follow_up_questions=[],
                provider=self.provider_name,
            )

        except Exception as error:
            return AIReasoning(
                executive_summary=f"Google Gemini request failed ({self.model}): {error}",
                confidence="Low",
                risks=["The API key may be invalid, the model name may be wrong, or the request timed out."],
                follow_up_questions=[
                    f"Tried model: {self.model}. If 404, try 'gemini-1.5-flash' or 'gemini-2.5-flash' in Settings.",
                ],
                provider=self.provider_name,
            )

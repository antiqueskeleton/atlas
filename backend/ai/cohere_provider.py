from backend.ai.base_provider import AIProvider
from backend.ai.ai_reasoning_parser import AIReasoningParser
from backend.models.ai_reasoning import AIReasoning


class CohereProvider(AIProvider):
    provider_name = "Cohere"
    model = "command-r-plus"

    def __init__(self):
        self.api_key = None
        self.model = self.__class__.model
        self.parser = AIReasoningParser()

    def ask(self, prompt: str, context: str | None = None) -> AIReasoning:
        if not self.api_key:
            return AIReasoning(
                executive_summary="Cohere provider is selected but no API key is configured.",
                confidence="Low",
                risks=["Atlas cannot make a live Cohere request without an API key."],
                follow_up_questions=["Add a Cohere API key in Settings."],
                provider=self.provider_name,
                is_error=True,
            )

        try:
            import cohere
            client = cohere.ClientV2(api_key=self.api_key)
            response = client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(
                block.text for block in response.message.content if block.type == "text"
            ) if response.message.content else ""
            return self.parser.parse(text=text, provider=self.provider_name)

        except ImportError:
            return AIReasoning(
                executive_summary="The 'cohere' package is not installed. Run: pip install cohere",
                confidence="Low",
                risks=["Missing dependency."],
                follow_up_questions=[],
                provider=self.provider_name,
                is_error=True,
            )

        except Exception as error:
            return AIReasoning(
                executive_summary=f"Cohere request failed ({self.model}): {error}",
                confidence="Low",
                risks=["The API key may be invalid or the request timed out."],
                follow_up_questions=[
                    "Check the Cohere API key in Settings.",
                    "Models: command-r-plus, command-r, command-a-03-2025",
                ],
                provider=self.provider_name,
                is_error=True,
            )

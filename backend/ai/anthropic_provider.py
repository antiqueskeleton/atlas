from backend.ai.base_provider import AIProvider
from backend.ai.ai_reasoning_parser import AIReasoningParser
from backend.models.ai_reasoning import AIReasoning


class AnthropicProvider(AIProvider):
    provider_name = "Anthropic"
    model = "claude-sonnet-4-6"

    def __init__(self):
        self.api_key = None
        self.parser = AIReasoningParser()

    def set_api_key(self, api_key):
        self.api_key = api_key

    def ask(self, prompt: str, context: str | None = None) -> AIReasoning:
        if not self.api_key:
            return AIReasoning(
                executive_summary="Anthropic provider is selected but no API key is configured.",
                confidence="Low",
                risks=["Atlas cannot make a live Anthropic request without an API key."],
                follow_up_questions=["Add an Anthropic API key in Settings."],
                provider=self.provider_name,
            )

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            message = client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            text = next(
                (block.text for block in message.content if block.type == "text"),
                "",
            )
            return self.parser.parse(text=text, provider=self.provider_name)

        except ImportError:
            return AIReasoning(
                executive_summary="The 'anthropic' package is not installed. Run: pip install anthropic",
                confidence="Low",
                risks=["Missing dependency."],
                follow_up_questions=[],
                provider=self.provider_name,
            )

        except Exception as error:
            return AIReasoning(
                executive_summary=f"Anthropic request failed: {error}",
                confidence="Low",
                risks=["The API key may be invalid or the request timed out."],
                follow_up_questions=["Check the Anthropic API key in Settings."],
                provider=self.provider_name,
            )

from backend.ai.base_provider import AIProvider
from backend.ai.ai_reasoning_parser import AIReasoningParser
from backend.models.ai_reasoning import AIReasoning
from backend.usage.usage_tracker import record_usage


class CohereProvider(AIProvider):
    provider_name = "Cohere"
    model = "command-a-03-2025"

    # Cohere RETIRED the undated aliases (confirmed live 2026-07-13: bare
    # "command-r-plus" now 404s while its dated successor works) — and the
    # old alias may live on in users' saved Settings, so it must be mapped
    # here, not just changed as the default, or the saved override keeps
    # re-breaking the provider forever.
    _RETIRED_ALIASES = {
        "command-r-plus": "command-r-plus-08-2024",
        "command-r": "command-r-08-2024",
    }

    def __init__(self):
        self.api_key = None
        self.model = self.__class__.model
        self.parser = AIReasoningParser()

    def set_model(self, model: str):
        if model:
            self.model = self._RETIRED_ALIASES.get(model.strip(), model.strip())

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
            record_usage(self.provider_name, self.model, response)
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
                    "Models: command-a-03-2025, command-r-plus-08-2024, "
                    "command-r7b-12-2024",
                ],
                provider=self.provider_name,
                is_error=True,
            )

from backend.ai.base_provider import AIProvider
from backend.ai.ai_reasoning_parser import AIReasoningParser
from backend.models.ai_reasoning import AIReasoning
from backend.usage.usage_tracker import record_usage


class PerplexityProvider(AIProvider):
    provider_name = "Perplexity"
    model = "sonar"
    _base_url = "https://api.perplexity.ai"

    def __init__(self):
        self.api_key = None
        self.model = self.__class__.model
        self.parser = AIReasoningParser()

    def ask(self, prompt: str, context: str | None = None) -> AIReasoning:
        if not self.api_key:
            return AIReasoning(
                executive_summary="Perplexity provider is selected but no API key is configured.",
                confidence="Low",
                risks=["Atlas cannot make a live Perplexity request without an API key."],
                follow_up_questions=["Add a Perplexity API key in Settings."],
                provider=self.provider_name,
                is_error=True,
            )

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, base_url=self._base_url)
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            text = response.choices[0].message.content or ""
            record_usage(self.provider_name, self.model, response)
            reasoning = self.parser.parse(text=text, provider=self.provider_name)
            # #96: Perplexity returns the source URLs it grounded the answer
            # on with every response — previously discarded. The openai SDK
            # keeps unknown top-level fields, so they're recoverable from the
            # response object; extraction failures must never sink a response
            # that already succeeded.
            reasoning.citations = _extract_citations(response)
            return reasoning

        except Exception as error:
            return AIReasoning(
                executive_summary=f"Perplexity request failed ({self.model}): {error}",
                confidence="Low",
                risks=["The API key may be invalid or the request timed out."],
                follow_up_questions=[
                    "Check the Perplexity API key in Settings.",
                    "Current models: sonar, sonar-pro, sonar-reasoning",
                ],
                provider=self.provider_name,
                is_error=True,
            )


def _extract_citations(response) -> list[str]:
    """Pull cited source URLs off a Perplexity chat response. The API
    returns them as a top-level "citations" list of URLs (and newer models
    also as "search_results" objects); the openai SDK surfaces unknown
    fields via attribute access / model_extra. Defensive by design — an
    extraction surprise returns [] rather than raising."""
    urls: list[str] = []
    try:
        raw = getattr(response, "citations", None)
        if not raw and getattr(response, "model_extra", None):
            raw = response.model_extra.get("citations")
        for item in raw or []:
            if isinstance(item, str) and item.startswith("http"):
                urls.append(item)

        results = getattr(response, "search_results", None)
        if not results and getattr(response, "model_extra", None):
            results = response.model_extra.get("search_results")
        for item in results or []:
            url = item.get("url", "") if isinstance(item, dict) else getattr(item, "url", "")
            if isinstance(url, str) and url.startswith("http"):
                urls.append(url)
    except Exception:
        return []

    seen: set[str] = set()
    unique = [u for u in urls if not (u in seen or seen.add(u))]
    return unique[:20]

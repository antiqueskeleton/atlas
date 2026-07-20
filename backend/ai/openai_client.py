from openai import OpenAI

from backend.ai.prompt_result import PromptResult
from backend.usage.usage_tracker import record_usage


class OpenAIClient:
    def __init__(self, api_key: str, model: str = "gpt-4.1-mini"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate(self, prompt: str) -> PromptResult:
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            temperature=0.2,
        )

        # Usage is metered here rather than in OpenAIProvider because the raw
        # response (and its token counts) never leaves this client.
        record_usage("OpenAI", self.model, response)

        return PromptResult(
            prompt=prompt,
            response=response.output_text,
            provider="OpenAI",
        )
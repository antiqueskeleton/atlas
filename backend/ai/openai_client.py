from openai import OpenAI

from backend.ai.prompt_result import PromptResult


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

        return PromptResult(
            prompt=prompt,
            response=response.output_text,
            provider="OpenAI",
        )
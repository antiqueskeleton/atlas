from openai import OpenAI

from backend.ai.prompt_result import PromptResult


class OpenAIClient:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def generate(self, prompt: str) -> PromptResult:
        response = self.client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            temperature=0.2,
        )

        return PromptResult(
            prompt=prompt,
            response=response.output_text,
            provider="OpenAI",
        )
from abc import ABC, abstractmethod

from backend.models.ai_reasoning import AIReasoning


class AIProvider(ABC):
    provider_name = "Base Provider"
    model = ""

    def set_api_key(self, api_key: str):
        self.api_key = api_key

    def set_model(self, model: str):
        if model:
            self.model = model

    @abstractmethod
    def ask(self, prompt: str, context: str | None = None) -> AIReasoning:
        pass
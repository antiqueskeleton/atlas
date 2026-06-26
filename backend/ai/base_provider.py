from abc import ABC, abstractmethod

from backend.models.ai_reasoning import AIReasoning


class AIProvider(ABC):
    provider_name = "Base Provider"

    @abstractmethod
    def ask(self, prompt: str, context: str | None = None) -> AIReasoning:
        pass
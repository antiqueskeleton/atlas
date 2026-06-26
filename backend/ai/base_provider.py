from abc import ABC, abstractmethod


class AIProvider(ABC):
    provider_name = "Base Provider"

    @abstractmethod
    def ask(self, prompt: str, context: str | None = None) -> str:
        pass
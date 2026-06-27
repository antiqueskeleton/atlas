from backend.ai.mock_provider import MockAIProvider
from backend.ai.openai_provider import OpenAIProvider


class ProviderRegistry:
    def __init__(self):
        self.providers = {
            "mock": MockAIProvider,
            "openai": OpenAIProvider,
        }

    def create_provider(self, provider_key):
        if provider_key not in self.providers:
            raise ValueError(f"Unknown provider: {provider_key}")

        return self.providers[provider_key]()

    def list_provider_keys(self):
        return list(self.providers.keys())
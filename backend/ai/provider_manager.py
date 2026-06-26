from backend.ai.mock_provider import MockAIProvider


class ProviderManager:
    def __init__(self):
        self.providers = {
            "mock": MockAIProvider(),
        }
        self.active_provider_name = "mock"

    def get_active_provider(self):
        return self.providers[self.active_provider_name]

    def set_active_provider(self, provider_name: str):
        if provider_name not in self.providers:
            raise ValueError(f"Unknown AI provider: {provider_name}")

        self.active_provider_name = provider_name

    def list_providers(self):
        return list(self.providers.keys())
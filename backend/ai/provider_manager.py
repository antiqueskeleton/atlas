from backend.ai.provider_registry import ProviderRegistry


class ProviderManager:
    def __init__(self):
        self.registry = ProviderRegistry()
        self.active_provider_name = "mock"

    def get_active_provider(self):
        return self.registry.create_provider(self.active_provider_name)

    def set_active_provider(self, provider_name: str):
        if provider_name not in self.registry.list_provider_keys():
            raise ValueError(f"Unknown AI provider: {provider_name}")

        self.active_provider_name = provider_name

    def list_providers(self):
        return self.registry.list_provider_keys()
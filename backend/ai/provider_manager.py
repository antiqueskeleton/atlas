from backend.ai.provider_registry import ProviderRegistry


class ProviderManager:
    def __init__(self):
        self.registry = ProviderRegistry()
        self.active_provider_name = "mock"
        self.api_keys = {}

    def get_active_provider(self):
        provider = self.registry.create_provider(self.active_provider_name)

        api_key = self.api_keys.get(self.active_provider_name)

        if hasattr(provider, "set_api_key"):
            provider.set_api_key(api_key)

        return provider

    def set_active_provider(self, provider_name: str):
        if provider_name not in self.registry.list_provider_keys():
            raise ValueError(f"Unknown AI provider: {provider_name}")

        self.active_provider_name = provider_name

    def list_providers(self):
        return self.registry.list_provider_keys()

    def set_provider_api_key(self, provider_name: str, api_key: str):
        self.api_keys[provider_name] = api_key

    def get_provider_api_key(self, provider_name: str):
        return self.api_keys.get(provider_name)
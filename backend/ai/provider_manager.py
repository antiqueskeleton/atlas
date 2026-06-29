from backend.ai.provider_registry import ProviderRegistry


class ProviderManager:
    def __init__(self):
        self.registry = ProviderRegistry()
        self.active_provider_name = "mock"
        self.api_keys: dict[str, str] = {}
        self.models: dict[str, str] = {}

    def get_active_provider(self):
        provider = self.registry.create_provider(self.active_provider_name)

        api_key = self.api_keys.get(self.active_provider_name)
        if api_key:
            provider.set_api_key(api_key)

        model = self.models.get(self.active_provider_name)
        if model:
            provider.set_model(model)

        return provider

    def set_active_provider(self, provider_name: str):
        if provider_name not in self.registry.list_provider_keys():
            raise ValueError(f"Unknown AI provider: {provider_name}")
        self.active_provider_name = provider_name

    def list_providers(self):
        return self.registry.list_provider_keys()

    def set_provider_api_key(self, provider_name: str, api_key: str):
        self.api_keys[provider_name] = api_key

    def get_provider_api_key(self, provider_name: str) -> str:
        return self.api_keys.get(provider_name, "")

    def set_provider_model(self, provider_name: str, model: str):
        self.models[provider_name] = model

    def get_provider_model(self, provider_name: str) -> str:
        return self.models.get(provider_name, "")

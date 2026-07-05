from backend.volume.volume_provider_registry import VolumeProviderRegistry


class VolumeProviderManager:
    """Mirrors backend/ai/provider_manager.py's ProviderManager — credential
    (service-account JSON path, or a future paid-tool API key) and site_url
    stand in for api_key/model."""

    def __init__(self):
        self.registry = VolumeProviderRegistry()
        self.credentials: dict[str, str] = {}
        self.site_urls: dict[str, str] = {}

    def get_provider(self, provider_name: str):
        provider = self.registry.create_provider(provider_name)
        credential = self.credentials.get(provider_name)
        if credential:
            provider.set_credential(credential)
        site_url = self.site_urls.get(provider_name)
        if site_url:
            provider.set_site_url(site_url)
        return provider

    def list_providers(self):
        return self.registry.list_provider_keys()

    def set_provider_credential(self, provider_name: str, credential: str):
        self.credentials[provider_name] = credential

    def get_provider_credential(self, provider_name: str) -> str:
        return self.credentials.get(provider_name, "")

    def set_provider_site_url(self, provider_name: str, site_url: str):
        self.site_urls[provider_name] = site_url

    def get_provider_site_url(self, provider_name: str) -> str:
        return self.site_urls.get(provider_name, "")

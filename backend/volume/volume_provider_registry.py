from backend.volume.gsc_provider import GoogleSearchConsoleProvider


class VolumeProviderRegistry:
    """Mirrors backend/ai/provider_registry.py's ProviderRegistry — a fixed
    map of provider key -> class, plus one paid tool to be added here later
    (SEMrush/Ahrefs/etc.) the same way a new AI provider gets added."""

    def __init__(self):
        self.providers = {
            "google_search_console": GoogleSearchConsoleProvider,
        }

    def create_provider(self, provider_key):
        if provider_key not in self.providers:
            raise ValueError(f"Unknown volume provider: {provider_key}")
        return self.providers[provider_key]()

    def list_provider_keys(self):
        return list(self.providers.keys())

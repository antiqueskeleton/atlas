from abc import ABC, abstractmethod


class PlatformProvider(ABC):
    """
    A source of real, current competitive-presence data for one external
    platform (YouTube, Reddit, retailer product listings, …), used by the
    Targeted Review page (#25) to explain WHY AI models see some brands more
    than others — with actual platform numbers, not inferences from AI
    response text like the rest of Atlas.

    Mirrors backend/volume/base_volume_provider.py's VolumeProvider pattern:
    credentials injected by a caller that read them from ConfigService, and
    every fetch returns an in-band-error dict (an "error" key that is empty
    on success) rather than raising — a platform being down or unconfigured
    must degrade to a visible message, never crash a collection loop that
    still has other brands/platforms to process.
    """
    platform_name = "Base Platform"

    # field_key -> human label, e.g. {"api_key": "API Key"}. The Settings
    # page renders one input per entry, so adding a credential field to a
    # provider automatically surfaces it in the UI. Empty dict means the
    # platform needs no credential (retailer scraping).
    credential_fields: dict[str, str] = {}

    def __init__(self):
        self.credentials: dict[str, str] = {}

    def set_credentials(self, credentials: dict[str, str]):
        self.credentials = credentials or {}

    def missing_credentials(self) -> list[str]:
        """Labels of credential fields that are required but not set."""
        return [
            label for key, label in self.credential_fields.items()
            if not self.credentials.get(key)
        ]

    @abstractmethod
    def fetch_brand_presence(self, brand: str) -> dict:
        """
        Fetches this platform's presence metrics for one brand.

        Returns a dict whose exact metric keys are platform-specific (the
        repository stores it as JSON verbatim), but every provider must
        include:
            brand: str      — echoed back
            platform: str   — self.platform_name
            error: str      — empty on success, short message on failure
        """
        raise NotImplementedError

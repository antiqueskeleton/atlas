from abc import ABC, abstractmethod


class VolumeProvider(ABC):
    """
    A source of real-world search-query volume data, used to sanity-check
    Atlas's hand-curated prompt library against genuine query demand (#61).
    Mirrors backend/ai/base_provider.py's AIProvider pattern so credential
    management, Settings UI, and testing all follow the same shape as the
    existing AI providers.
    """
    provider_name = "Base Volume Provider"

    def __init__(self):
        self.credential = None  # provider-specific: e.g. a service-account JSON file path
        self.site_url = None    # the property/domain being queried

    def set_credential(self, credential: str):
        self.credential = credential

    def set_site_url(self, site_url: str):
        self.site_url = site_url

    @abstractmethod
    def get_query_volumes(self, days: int = 90) -> dict:
        """
        Fetches real search queries for self.site_url over the trailing
        `days` days.

        Returns a dict (same in-band-error shape as
        backend/intelligence/web_scraper.py's scrape_domain(), since this is
        also fundamentally "call an external HTTP API, report what happened"):
            queries: list[dict] — each {"query": str, "clicks": int, "impressions": int}
            error: str — empty on success, a short message on failure
                         (no credential configured, bad credential, API error)
        """
        raise NotImplementedError

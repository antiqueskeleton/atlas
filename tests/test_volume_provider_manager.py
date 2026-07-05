"""
Tests for backend/volume/volume_provider_manager.py + volume_provider_registry.py
(#61) — mirrors backend/ai/provider_manager.py's ProviderManager pattern for
keyword-volume data sources (credential + site_url stand in for api_key/model).
"""
from backend.volume.volume_provider_manager import VolumeProviderManager
from backend.volume.volume_provider_registry import VolumeProviderRegistry
from backend.volume.gsc_provider import GoogleSearchConsoleProvider


def test_registry_creates_known_provider():
    registry = VolumeProviderRegistry()
    provider = registry.create_provider("google_search_console")
    assert isinstance(provider, GoogleSearchConsoleProvider)


def test_registry_rejects_unknown_provider():
    registry = VolumeProviderRegistry()
    try:
        registry.create_provider("bogus")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_registry_lists_provider_keys():
    registry = VolumeProviderRegistry()
    assert "google_search_console" in registry.list_provider_keys()


def test_manager_get_provider_configures_credential_and_site_url():
    mgr = VolumeProviderManager()
    mgr.set_provider_credential("google_search_console", "/path/to/key.json")
    mgr.set_provider_site_url("google_search_console", "https://example.com/")

    provider = mgr.get_provider("google_search_console")
    assert provider.credential == "/path/to/key.json"
    assert provider.site_url == "https://example.com/"


def test_manager_get_provider_with_no_credential_set_leaves_it_none():
    mgr = VolumeProviderManager()
    provider = mgr.get_provider("google_search_console")
    assert provider.credential is None
    assert provider.site_url is None


def test_manager_get_set_credential_roundtrip():
    mgr = VolumeProviderManager()
    assert mgr.get_provider_credential("google_search_console") == ""
    mgr.set_provider_credential("google_search_console", "/a/b.json")
    assert mgr.get_provider_credential("google_search_console") == "/a/b.json"


def test_manager_get_set_site_url_roundtrip():
    mgr = VolumeProviderManager()
    assert mgr.get_provider_site_url("google_search_console") == ""
    mgr.set_provider_site_url("google_search_console", "sc-domain:example.com")
    assert mgr.get_provider_site_url("google_search_console") == "sc-domain:example.com"


def test_manager_list_providers_matches_registry():
    mgr = VolumeProviderManager()
    assert mgr.list_providers() == mgr.registry.list_provider_keys()

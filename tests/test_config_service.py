"""
Tests for backend/services/config_service.py's volume-provider credential
storage (#61) — get/set_volume_credential and get/set_volume_site_url.

IMPORTANT: ConfigService always resolves its user config path from the
APPDATA env var (no constructor override), and would otherwise read/write
the REAL user's %APPDATA%\\Atlas\\settings.json. Every test here redirects
APPDATA to a pytest tmp_path via monkeypatch BEFORE constructing
ConfigService, so the real settings file is never touched.
"""
from backend.services.config_service import ConfigService


def _config(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    return ConfigService()


def test_volume_credential_defaults_to_empty_string(tmp_path, monkeypatch):
    cfg = _config(tmp_path, monkeypatch)
    assert cfg.get_volume_credential("google_search_console") == ""


def test_set_and_get_volume_credential_roundtrip(tmp_path, monkeypatch):
    cfg = _config(tmp_path, monkeypatch)
    cfg.set_volume_credential("google_search_console", "/path/to/key.json")
    assert cfg.get_volume_credential("google_search_console") == "/path/to/key.json"


def test_set_and_get_volume_site_url_roundtrip(tmp_path, monkeypatch):
    cfg = _config(tmp_path, monkeypatch)
    cfg.set_volume_site_url("google_search_console", "https://example.com/")
    assert cfg.get_volume_site_url("google_search_console") == "https://example.com/"


def test_volume_credential_persists_across_instances(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    cfg1 = ConfigService()
    cfg1.set_volume_credential("google_search_console", "/a/b.json")
    cfg1.set_volume_site_url("google_search_console", "sc-domain:example.com")

    cfg2 = ConfigService()  # fresh instance, same APPDATA -> reloads from disk
    assert cfg2.get_volume_credential("google_search_console") == "/a/b.json"
    assert cfg2.get_volume_site_url("google_search_console") == "sc-domain:example.com"


def test_volume_credential_does_not_disturb_existing_api_keys(tmp_path, monkeypatch):
    cfg = _config(tmp_path, monkeypatch)
    cfg.set_api_key("openai", "sk-real-key")
    cfg.set_volume_credential("google_search_console", "/a/b.json")

    assert cfg.get_api_key("openai") == "sk-real-key"
    assert cfg.get_volume_credential("google_search_console") == "/a/b.json"

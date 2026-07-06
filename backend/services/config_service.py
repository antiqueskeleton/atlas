import json
import os
from pathlib import Path


class ConfigService:
    def __init__(self):
        self._project_root = Path(__file__).resolve().parents[2]
        self._user_config_path = self._resolve_user_config()
        self.settings = self._load()

    # ── Public API ────────────────────────────────────────────────────────────

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self._save()

    def get_api_key(self, provider_name: str) -> str:
        return self.settings.get("api_keys", {}).get(provider_name, "")

    def set_api_key(self, provider_name: str, api_key: str):
        if "api_keys" not in self.settings:
            self.settings["api_keys"] = {}
        self.settings["api_keys"][provider_name] = api_key
        self._save()

    def get_target_brand(self) -> str:
        return self.settings.get("target_brand", "")

    def set_target_brand(self, brand: str):
        self.settings["target_brand"] = brand
        self._save()

    def get_model(self, provider_name: str) -> str:
        return self.settings.get("models", {}).get(provider_name, "")

    def set_model(self, provider_name: str, model: str):
        if "models" not in self.settings:
            self.settings["models"] = {}
        self.settings["models"][provider_name] = model
        self._save()

    def get_volume_credential(self, provider_name: str) -> str:
        """Returns the stored credential for a volume provider — for
        Google Search Console this is a file PATH to a service-account
        JSON key, not the key contents itself (keeps the private key out
        of settings.json; the user manages that file like any other
        credential file on disk)."""
        return self.settings.get("volume_credentials", {}).get(provider_name, "")

    def set_volume_credential(self, provider_name: str, credential: str):
        if "volume_credentials" not in self.settings:
            self.settings["volume_credentials"] = {}
        self.settings["volume_credentials"][provider_name] = credential
        self._save()

    def get_volume_site_url(self, provider_name: str) -> str:
        return self.settings.get("volume_site_urls", {}).get(provider_name, "")

    def set_volume_site_url(self, provider_name: str, site_url: str):
        if "volume_site_urls" not in self.settings:
            self.settings["volume_site_urls"] = {}
        self.settings["volume_site_urls"][provider_name] = site_url
        self._save()

    def get_platform_credential(self, platform: str, field: str) -> str:
        """Targeted Review platform credentials (#25) — two-level (platform →
        field) because a platform can need multiple fields (Reddit: client
        id + secret), unlike AI/volume providers' single api_key/credential."""
        return (self.settings.get("platform_credentials", {})
                .get(platform, {}).get(field, ""))

    def set_platform_credential(self, platform: str, field: str, value: str):
        creds = self.settings.setdefault("platform_credentials", {})
        creds.setdefault(platform, {})[field] = value
        self._save()

    def get_user_config_path(self) -> Path:
        return self._user_config_path

    # ── Internal ──────────────────────────────────────────────────────────────

    def _resolve_user_config(self) -> Path:
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / ".config"
        config_dir = base / "Atlas"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "settings.json"

    def _load(self) -> dict:
        settings = {}

        # Load project defaults first
        default_path = self._project_root / "config" / "settings.json"
        if default_path.exists():
            with default_path.open("r", encoding="utf-8") as f:
                settings.update(json.load(f))

        # User config overrides defaults (API keys live here only)
        if self._user_config_path.exists():
            with self._user_config_path.open("r", encoding="utf-8") as f:
                settings.update(json.load(f))

        return settings

    def _save(self):
        # Only write user-owned keys to user config (never back to project config)
        user_keys = {"target_brand", "api_keys", "models", "volume_credentials",
                     "volume_site_urls", "platform_credentials"}
        user_data = {k: v for k, v in self.settings.items() if k in user_keys}
        with self._user_config_path.open("w", encoding="utf-8") as f:
            json.dump(user_data, f, indent=2)

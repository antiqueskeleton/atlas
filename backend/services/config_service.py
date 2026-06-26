import json
from pathlib import Path


class ConfigService:

    def __init__(self):

        self.project_root = Path(__file__).resolve().parents[2]

        config_path = self.project_root / "config" / "settings.json"

        with config_path.open("r", encoding="utf-8") as file:
            self.settings = json.load(file)

    def get(self, key, default=None):
        return self.settings.get(key, default)
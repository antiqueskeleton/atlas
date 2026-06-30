"""
Atlas AI — lightweight update checker.

Runs in a background QThread on startup.  If a newer version is available
it emits update_available(version, url) which the main window connects to
in order to show a non-blocking status-bar notification.

Manifest format (hosted JSON):
  {
    "version": "0.3",
    "download_url": "https://example.com/AtlasAI-v0.3-Setup.exe",
    "release_notes": "What changed in this release."
  }

Set ATLAS_UPDATE_URL to point at your hosted manifest.  If the constant is
empty the check is skipped silently.
"""

import json
import urllib.request
import urllib.error
from PySide6.QtCore import QThread, Signal

APP_VERSION = "0.2"

ATLAS_UPDATE_URL = "https://raw.githubusercontent.com/antiqueskeleton/atlas/master/update_manifest.json"


class UpdateChecker(QThread):
    update_available = Signal(str, str, str)  # version, url, notes

    def run(self):
        if not ATLAS_UPDATE_URL:
            return
        try:
            req = urllib.request.Request(
                ATLAS_UPDATE_URL,
                headers={"User-Agent": f"AtlasAI/{APP_VERSION}"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            remote_ver = data.get("version", "")
            dl_url = data.get("download_url", "")
            notes = data.get("release_notes", "")

            if remote_ver and _is_newer(remote_ver, APP_VERSION):
                self.update_available.emit(remote_ver, dl_url, notes)
        except Exception:
            pass  # network errors are silently ignored — never crash on update check

    @staticmethod
    def _is_newer(remote: str, current: str) -> bool:
        try:
            def parts(v): return [int(x) for x in v.split(".")]
            return parts(remote) > parts(current)
        except (ValueError, AttributeError):
            return False



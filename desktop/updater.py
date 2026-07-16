"""
Atlas AI — lightweight update checker.

Runs in a background QThread on startup.  If a newer version is available
it emits update_available(version, url, notes) which the main window connects
to in order to show a non-blocking status-bar notification.

Also supports a manual "Check for Updates" trigger (Help menu): a fresh
UpdateChecker instance connects to all three outcome signals — update_available,
up_to_date, and check_failed — so a user-initiated check always gets visible
feedback, unlike the silent-unless-found startup check.

Manifest format (hosted JSON):
  {
    "version": "0.3",
    "download_url": "https://example.com/AtlasAI-v0.3-Setup.exe",
    "release_notes": "What changed in this release."
  }

Set ATLAS_UPDATE_URL to point at your hosted manifest.  If the constant is
empty the check is skipped silently for the automatic startup check, but
still reports check_failed for a manual trigger.
"""

import json
import urllib.request
import urllib.error
from PySide6.QtCore import QThread, Signal

APP_VERSION = "1.0.0"

ATLAS_UPDATE_URL = "https://raw.githubusercontent.com/antiqueskeleton/atlas/main/update_manifest.json"


class UpdateChecker(QThread):
    update_available = Signal(str, str, str)  # version, url, notes
    up_to_date        = Signal(str)             # current version — already latest
    check_failed      = Signal(str)             # error message

    def run(self):
        if not ATLAS_UPDATE_URL:
            self.check_failed.emit("Update checking is not configured.")
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

            # BUG FIX: this previously called the bare name `_is_newer(...)`
            # instead of `self._is_newer(...)` — since _is_newer is a method
            # on this class, the bare call raised NameError on every single
            # check, which the except-block below silently swallowed. The
            # auto-updater has never successfully detected a real update
            # because of this, independent of whether ATLAS_UPDATE_URL was
            # correct. Confirmed via direct test 2026-07-02.
            if remote_ver and self._is_newer(remote_ver, APP_VERSION):
                self.update_available.emit(remote_ver, dl_url, notes)
            else:
                self.up_to_date.emit(APP_VERSION)
        except Exception as exc:
            self.check_failed.emit(str(exc))

    @staticmethod
    def _is_newer(remote: str, current: str) -> bool:
        try:
            def parts(v): return [int(x) for x in v.split(".")]
            return parts(remote) > parts(current)
        except (ValueError, AttributeError):
            return False

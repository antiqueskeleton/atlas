import os
from pathlib import Path


def get_db_path() -> Path:
    """Return the user-level database path, creating the directory if needed.

    Uses %APPDATA%\\Atlas on Windows, ~/.config/Atlas elsewhere.
    Safe to call at module load time — no side effects beyond mkdir.
    """
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / ".config"
    db_dir = base / "Atlas"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "atlas.db"


def get_data_dir() -> Path:
    """Return the bundled data directory.

    When running from a PyInstaller exe, data files are extracted to sys._MEIPASS.
    When running from source, returns the project-root /data directory.
    """
    import sys
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "data"
    return Path(__file__).resolve().parents[2] / "data"

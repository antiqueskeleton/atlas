import os
import sys
from pathlib import Path


def get_db_path() -> Path:
    """Return the database path.

    When running as a PyInstaller exe (sys.frozen), data cannot be written next
    to the exe, so we store it in %APPDATA%\\Atlas on Windows.

    When running from source, we keep atlas.db inside the project at
    database/atlas.db — same location it always lived.  This means no data is
    ever lost when switching between development runs, and the file stays out of
    the packaged exe bundle.
    """
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / ".config"
        db_dir = base / "Atlas"
        db_dir.mkdir(parents=True, exist_ok=True)
        return db_dir / "atlas.db"

    # Running from source — project-relative path (original location)
    db_dir = Path(__file__).resolve().parents[2] / "database"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "atlas.db"


def get_logs_dir() -> Path:
    """Directory for diagnostic run logs (#75) — a sibling of the database
    file, so it's %APPDATA%\\Atlas\\logs when frozen, or database/logs when
    running from source."""
    d = get_db_path().parent / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_data_dir() -> Path:
    """Return the bundled data directory.

    When running from a PyInstaller exe, data files are extracted to sys._MEIPASS.
    When running from source, returns the project-root /data directory.
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "data"
    return Path(__file__).resolve().parents[2] / "data"

import os
import shutil
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
    """User-editable knowledge data (the CSVs: prompts, brands, features…).

    Frozen: %APPDATA%\\Atlas\\data, seeded from the bundled copies. This
    previously returned sys._MEIPASS/data — the install directory — where
    every Knowledge-page edit was silently DESTROYED by the next update
    (the installer replaces the whole install dir; confirmed data-loss bug,
    2026-07-20). User data now lives beside the database, which already
    proved this pattern.

    Source: project-root /data, unchanged.
    """
    if getattr(sys, "frozen", False):
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / ".config"
        user_data = base / "Atlas" / "data"
        _seed_user_data(user_data, Path(sys._MEIPASS) / "data")
        return user_data
    return Path(__file__).resolve().parents[2] / "data"


def _seed_user_data(user_data: Path, bundled: Path) -> None:
    """Copy each bundled data file the user doesn't have yet — a first run
    seeds everything; an upgrade adds files that are NEW in the release
    without touching any file the user already has (their edits always
    win over shipped defaults). A copy failure must never block startup —
    the app degrades to whatever files exist, same as a missing CSV."""
    try:
        user_data.mkdir(parents=True, exist_ok=True)
        if not bundled.is_dir():
            return
        for src in bundled.iterdir():
            if src.is_file() and not (user_data / src.name).exists():
                shutil.copy2(src, user_data / src.name)
    except OSError:
        pass

"""
Database backup + integrity checking (#92).

The single atlas.db file IS the product's asset — thousands of collected
responses that cannot be re-collected as-of their original dates. Until
now nothing backed it up and nothing verified it wasn't silently corrupt.

Backups use sqlite3's online backup API (safe while other connections are
open, unlike a raw file copy which can catch the database mid-write) into
<db_dir>/backups/atlas-YYYYMMDD-HHMMSS.db, rotated to the newest N. Runs
at every app launch but skips when a recent-enough backup already exists,
so frequent restarts don't churn the whole rotation in a day.

Also the prerequisite for the SharePoint sharing plan (#24): share these
rotated backup copies, never the live database file — SQLite over a
sync service invites corruption on the live file.
"""
from datetime import datetime
from pathlib import Path
import sqlite3

from backend.services.paths import get_db_path

_KEEP = 5
_MIN_INTERVAL_HOURS = 12


def backup_dir(db_path=None) -> Path:
    base = Path(db_path) if db_path else get_db_path()
    d = base.parent / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_backups(db_path=None) -> list[Path]:
    """Existing backups, newest first."""
    return sorted(backup_dir(db_path).glob("atlas-*.db"),
                  key=lambda p: p.name, reverse=True)


def create_backup(db_path=None, keep: int = _KEEP,
                  min_interval_hours: float = _MIN_INTERVAL_HOURS) -> tuple[Path | None, bool]:
    """
    Returns (backup_path, created). created is False when a fresh-enough
    backup already exists (its path is returned) or when the source
    database doesn't exist yet (None). Never raises — a failed backup must
    not block app startup; callers surface status via the Health card.
    """
    source = Path(db_path) if db_path else get_db_path()
    try:
        if not source.exists() or source.stat().st_size == 0:
            return None, False

        existing = list_backups(db_path)
        if existing:
            age_hours = (datetime.now().timestamp()
                         - existing[0].stat().st_mtime) / 3600
            if age_hours < min_interval_hours:
                return existing[0], False

        dest = backup_dir(db_path) / f"atlas-{datetime.now():%Y%m%d-%H%M%S}.db"
        src_conn = sqlite3.connect(source)
        dst_conn = sqlite3.connect(dest)
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

        for old in list_backups(db_path)[keep:]:
            try:
                old.unlink()
            except OSError:
                pass
        return dest, True
    except Exception:
        return None, False


def integrity_check(db_path=None) -> tuple[bool, str]:
    """PRAGMA integrity_check — (ok, detail). Detail is 'ok' on a healthy
    database, the first reported problem (or the error) otherwise."""
    source = Path(db_path) if db_path else get_db_path()
    try:
        conn = sqlite3.connect(source)
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
        finally:
            conn.close()
        detail = str(row[0]) if row else "no result"
        return detail == "ok", detail
    except Exception as exc:
        return False, str(exc)

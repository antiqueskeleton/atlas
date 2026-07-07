"""
Tests for backend/services/backup_service.py (#92) — rotating online
backups + integrity checking for the single-file database that IS the
product's asset.
"""
import os
import sqlite3
import time

from backend.services.backup_service import (
    create_backup, integrity_check, list_backups,
)


def _make_db(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (x TEXT)")
    conn.execute("INSERT INTO t VALUES ('data')")
    conn.commit()
    conn.close()
    return path


def test_create_backup_produces_readable_copy(tmp_path):
    db = _make_db(tmp_path / "atlas.db")
    path, created = create_backup(db_path=db)
    assert created is True
    assert path is not None and path.exists()
    # The copy is a real, openable database with the data intact
    assert sqlite3.connect(path).execute("SELECT x FROM t").fetchone() == ("data",)


def test_create_backup_skips_when_recent_backup_exists(tmp_path):
    db = _make_db(tmp_path / "atlas.db")
    first, created = create_backup(db_path=db)
    assert created is True
    second, created = create_backup(db_path=db)  # immediately after
    assert created is False
    assert second == first  # existing fresh backup returned, not duplicated


def test_create_backup_rotates_to_keep_newest(tmp_path):
    db = _make_db(tmp_path / "atlas.db")
    # Force 7 distinct backups by disabling the freshness skip
    for i in range(7):
        path, created = create_backup(db_path=db, keep=3, min_interval_hours=0)
        assert created is True
        # Distinct timestamped names need distinct seconds; nudge mtimes
        # instead of sleeping 1s per iteration.
        os.utime(path, (time.time() - (7 - i) * 60, time.time() - (7 - i) * 60))
        new_name = path.with_name(f"atlas-2026010{i}-000000.db")
        path.rename(new_name)
    backups = list_backups(db_path=db)
    assert len(backups) == 3
    assert backups[0].name == "atlas-20260106-000000.db"  # newest kept


def test_create_backup_handles_missing_source_gracefully(tmp_path):
    path, created = create_backup(db_path=tmp_path / "nonexistent.db")
    assert path is None and created is False


def test_integrity_check_ok_on_healthy_db(tmp_path):
    db = _make_db(tmp_path / "atlas.db")
    ok, detail = integrity_check(db_path=db)
    assert ok is True and detail == "ok"


def test_integrity_check_fails_on_garbage_file(tmp_path):
    bad = tmp_path / "atlas.db"
    bad.write_bytes(b"this is not a sqlite database at all" * 100)
    ok, detail = integrity_check(db_path=bad)
    assert ok is False
    assert detail  # carries an explanation, not a bare False

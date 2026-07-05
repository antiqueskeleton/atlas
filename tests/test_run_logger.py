"""
Tests for desktop/run_logger.py's RunLogger (#75) — a real, on-disk,
per-line-flushed log of a Visibility Collection run, written so a silently
stalled/crashed run leaves a forensic trail instead of just an in-memory
progress bar that vanishes with the process.

Isolated from the real logs directory via patching get_logs_dir to a
pytest tmp_path — never touches the real %APPDATA%\\Atlas\\logs (or
database/logs in dev mode).
"""
import os
from unittest.mock import patch

from desktop.run_logger import RunLogger, _prune_old_logs, _MAX_KEPT_LOGS


def _isolated(tmp_path):
    return patch("desktop.run_logger.get_logs_dir", return_value=tmp_path)


def test_start_creates_log_file_with_header(tmp_path):
    with _isolated(tmp_path):
        rl = RunLogger()
        path = rl.start(["openai", "anthropic"], 10, "Best Portable Generator")
        rl.close("completed")

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "Run started" in text
    assert "providers=['openai', 'anthropic']" in text
    assert "prompt_count=10" in text
    assert "prompt_set=Best Portable Generator" in text
    assert "Run finished" in text
    assert "status=completed" in text


def test_info_and_error_lines_are_flushed_before_close(tmp_path):
    """
    The whole point of this feature is surviving a crash — a line must be
    on disk the moment it's logged, not just buffered until close(). Read
    the file back WITHOUT closing first to confirm this.
    """
    with _isolated(tmp_path):
        rl = RunLogger()
        path = rl.start(["openai"], 1, "Test")
        rl.info("a normal info line")
        rl.error("an error line")
        text_before_close = path.read_text(encoding="utf-8")
        rl.close("completed")

    assert "a normal info line" in text_before_close
    assert "an error line" in text_before_close


def test_methods_are_safe_no_ops_before_start_and_after_close(tmp_path):
    rl = RunLogger()
    rl.info("should not raise before start()")
    rl.error("should not raise before start()")

    with _isolated(tmp_path):
        rl.start(["openai"], 1, "Test")
        rl.close("completed")

    rl.info("should not raise after close()")  # must not resurrect the closed handler


def test_prune_keeps_only_the_most_recent_max_logs_minus_one(tmp_path):
    """
    _prune_old_logs() targets _MAX_KEPT_LOGS - 1 EXISTING files, leaving
    room for the new log file about to be created right after it runs —
    so the folder never holds more than _MAX_KEPT_LOGS total once the new
    file lands.
    """
    for i in range(_MAX_KEPT_LOGS + 5):
        p = tmp_path / f"visibility_run_{i:03d}.log"
        p.write_text("x")
        os.utime(p, (i, i))

    with _isolated(tmp_path):
        _prune_old_logs()

    remaining = sorted(tmp_path.glob("visibility_run_*.log"))
    assert len(remaining) == _MAX_KEPT_LOGS - 1
    assert not (tmp_path / "visibility_run_000.log").exists()
    assert (tmp_path / f"visibility_run_{_MAX_KEPT_LOGS + 4:03d}.log").exists()


def test_prune_is_a_no_op_when_under_the_limit(tmp_path):
    for i in range(3):
        (tmp_path / f"visibility_run_{i:03d}.log").write_text("x")

    with _isolated(tmp_path):
        _prune_old_logs()

    assert len(list(tmp_path.glob("visibility_run_*.log"))) == 3


def test_start_prunes_old_logs_so_folder_never_exceeds_max_after_creation(tmp_path):
    for i in range(_MAX_KEPT_LOGS + 3):
        p = tmp_path / f"visibility_run_{i:03d}.log"
        p.write_text("x")
        os.utime(p, (i, i))

    with _isolated(tmp_path):
        rl = RunLogger()
        rl.start(["openai"], 1, "Test")
        rl.close("completed")

    remaining = list(tmp_path.glob("visibility_run_*.log"))
    assert len(remaining) == _MAX_KEPT_LOGS

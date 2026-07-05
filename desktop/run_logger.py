"""
Diagnostic logging for Visibility Collection runs (#75).

Trigger: a real 5-provider, 507-prompt run stalled at ~80% progress with no
way to tell whether it crashed or the PC slept again — Atlas kept no
forensic trail once a run stopped responding, only an in-memory progress
bar that vanishes with the process. RunLogger writes a real file to disk,
flushed after every line (via the standard logging module, which flushes
each handler after every emit), so if a run silently stalls again, the log
up to the last successful line survives and can be found and shared.

One log file per run, named by start timestamp. Safe to use from multiple
provider threads at once (Python's logging module locks each handler
internally) since _RunWorker runs providers concurrently.
"""
import logging
from datetime import datetime
from pathlib import Path

from backend.services.paths import get_logs_dir

_MAX_KEPT_LOGS = 20


def _prune_old_logs():
    """
    Called right before creating a new log file, so it keeps at most
    _MAX_KEPT_LOGS - 1 EXISTING files — leaving room for the one about to
    be created, so the folder never holds more than _MAX_KEPT_LOGS total.
    """
    keep = _MAX_KEPT_LOGS - 1
    logs = sorted(get_logs_dir().glob("visibility_run_*.log"), key=lambda p: p.stat().st_mtime)
    for old in logs[:-keep] if len(logs) > keep else []:
        try:
            old.unlink()
        except OSError:
            pass


class RunLogger:
    def __init__(self):
        self._logger: logging.Logger | None = None
        self._handler: logging.FileHandler | None = None
        self.log_path: Path | None = None

    def start(self, providers: list[str], prompt_count: int, label: str) -> Path:
        _prune_old_logs()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_path = get_logs_dir() / f"visibility_run_{timestamp}.log"

        self._logger = logging.getLogger(f"atlas.visibility_run.{timestamp}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False
        self._handler = logging.FileHandler(self.log_path, encoding="utf-8")
        self._handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s"))
        self._logger.addHandler(self._handler)

        self.info(
            f"Run started — providers={providers}, prompt_count={prompt_count}, "
            f"prompt_set={label}"
        )
        return self.log_path

    def info(self, message: str):
        if self._logger:
            self._logger.info(message)

    def error(self, message: str):
        if self._logger:
            self._logger.error(message)

    def close(self, status: str):
        self.info(f"Run finished — status={status}")
        if self._handler:
            self._handler.close()
            self._logger.removeHandler(self._handler)
        self._logger = None
        self._handler = None

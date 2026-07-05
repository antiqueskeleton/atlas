"""
Tests for backend/visibility/visibility_runner.py's optional logger param
(#75) — confirms run_prompt_set() logs enough detail (per-prompt success/
error with timing, provider start/finish, cancellation) that a silent
stall's last line pinpoints where it died, without requiring the desktop
layer's RunLogger — logger is duck-typed (just needs .info()/.error()).
"""
from types import SimpleNamespace

from backend.visibility.visibility_runner import VisibilityRunner


class _FakeLogger:
    def __init__(self):
        self.info_lines: list[str] = []
        self.error_lines: list[str] = []

    def info(self, message):
        self.info_lines.append(message)

    def error(self, message):
        self.error_lines.append(message)


class _FakeProvider:
    provider_name = "FakeProvider"
    model = "fake-model"

    def __init__(self, results=None):
        self.calls: list[str] = []
        self._results = results  # optional list of "ok"/"error" per call

    def ask(self, prompt):
        self.calls.append(prompt)
        idx = len(self.calls) - 1
        if self._results and self._results[idx] == "error":
            return SimpleNamespace(is_error=True, executive_summary="")
        return SimpleNamespace(is_error=False, executive_summary=f"Fake answer to: {prompt}")


class _FakePM:
    def get_provider(self, name):
        return _FakeProvider()


def _runner():
    return VisibilityRunner(_FakePM())


def test_no_logger_does_not_raise():
    runner = _runner()
    provider = _FakeProvider()
    result = runner.run_prompt_set(
        prompts=["prompt one", "prompt two"], provider=provider, logger=None,
    )
    assert len(result["responses"]) == 2


def test_logger_records_start_and_finish_summary():
    runner = _runner()
    provider = _FakeProvider()
    logger = _FakeLogger()

    runner.run_prompt_set(prompts=["a", "b", "c"], provider=provider, logger=logger)

    assert any("starting 3 prompts" in line for line in logger.info_lines)
    assert any("finished" in line and "3 ok" in line and "0 error(s)" in line
               for line in logger.info_lines)


def test_logger_records_each_prompt_success_with_index_and_timing():
    runner = _runner()
    provider = _FakeProvider()
    logger = _FakeLogger()

    runner.run_prompt_set(prompts=["only prompt"], provider=provider, logger=logger)

    assert any("prompt 1/1 ok" in line for line in logger.info_lines)


def test_logger_records_prompt_errors_separately_from_successes():
    runner = _runner()
    provider = _FakeProvider(results=["ok", "error", "ok"])
    logger = _FakeLogger()

    runner.run_prompt_set(prompts=["p1", "p2", "p3"], provider=provider, logger=logger)

    assert any("prompt 2/3 ERROR" in line for line in logger.error_lines)
    assert any("finished" in line and "2 ok" in line and "1 error(s)" in line
               for line in logger.info_lines)


def test_logger_records_cancellation_point():
    runner = _runner()
    provider = _FakeProvider()
    logger = _FakeLogger()
    calls = {"n": 0}

    def cancelled():
        calls["n"] += 1
        return calls["n"] > 2  # cancel after the 2nd prompt completes

    result = runner.run_prompt_set(
        prompts=["p1", "p2", "p3", "p4"], provider=provider,
        cancelled=cancelled, logger=logger,
    )

    assert len(result["responses"]) == 2
    assert any("cancelled at prompt 3/4" in line for line in logger.info_lines)


def test_logger_lines_include_provider_name_for_multi_provider_diagnosis():
    """
    _RunWorker runs multiple providers concurrently against the SAME log
    file — every line must be attributable to a specific provider, or a
    stalled multi-provider run would be unreadable.
    """
    runner = _runner()
    provider = _FakeProvider()
    logger = _FakeLogger()

    runner.run_prompt_set(prompts=["p1"], provider=provider, logger=logger)

    assert all("[FakeProvider]" in line for line in logger.info_lines)

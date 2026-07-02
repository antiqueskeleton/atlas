"""
Tests for desktop/updater.py's UpdateChecker.

Regression test for a real, confirmed bug (found 2026-07-02): run() called
the bare name `_is_newer(...)` instead of `self._is_newer(...)`. Since
_is_newer is a method on the class, the bare call raised NameError on every
single check, silently swallowed by the surrounding except-block — meaning
the auto-updater had never successfully detected a real update, regardless
of whether the manifest URL was correct.
"""
from unittest.mock import patch, MagicMock
import json

from desktop.updater import UpdateChecker


def _fake_response(version, download_url="https://example.com/fake.exe", notes="test"):
    resp = MagicMock()
    resp.read.return_value = json.dumps({
        "version": version,
        "download_url": download_url,
        "release_notes": notes,
    }).encode("utf-8")
    resp.__enter__ = lambda self: resp
    resp.__exit__ = lambda self, *a: None
    return resp


def test_newer_remote_version_emits_update_available():
    checker = UpdateChecker()
    available = []
    checker.update_available.connect(lambda v, u, n: available.append((v, u, n)))

    with patch("urllib.request.urlopen", return_value=_fake_response("99.0")):
        checker.run()

    assert available == [("99.0", "https://example.com/fake.exe", "test")]


def test_older_or_equal_remote_version_emits_up_to_date_not_update_available():
    checker = UpdateChecker()
    available, up_to_date = [], []
    checker.update_available.connect(lambda v, u, n: available.append(v))
    checker.up_to_date.connect(lambda v: up_to_date.append(v))

    with patch("urllib.request.urlopen", return_value=_fake_response("0.1")):
        checker.run()

    assert available == []
    assert len(up_to_date) == 1


def test_network_error_emits_check_failed_not_a_crash():
    checker = UpdateChecker()
    failed = []
    checker.check_failed.connect(lambda e: failed.append(e))

    with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        checker.run()  # must not raise

    assert len(failed) == 1
    assert "timed out" in failed[0]


def test_is_newer_static_comparison_logic():
    assert UpdateChecker._is_newer("0.9", "0.8") is True
    assert UpdateChecker._is_newer("0.8", "0.8") is False
    assert UpdateChecker._is_newer("0.7", "0.8") is False
    assert UpdateChecker._is_newer("1.0", "0.8") is True
    assert UpdateChecker._is_newer("not-a-version", "0.8") is False

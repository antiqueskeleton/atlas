"""
Tests for desktop/sleep_guard.py (#56) — prevents Windows from sleeping
during a long Visibility collection. Confirms both the real Win32 behavior
(this dev environment is Windows, so the actual API call is exercised, not
just mocked) and that failures/non-Windows platforms degrade to a silent
no-op rather than ever crashing a collection run.
"""
import ctypes
import sys
from unittest.mock import patch

import pytest

from desktop.sleep_guard import allow_sleep, prevent_sleep

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


def _unsigned(v: int) -> int:
    return v & 0xFFFFFFFF


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 execution state API only exists on Windows")
def test_prevent_sleep_actually_sets_the_real_windows_execution_state():
    """Real integration check, not a mock — SetThreadExecutionState(0) is
    documented to return the previous state without changing it, so this
    reads back exactly what prevent_sleep() actually set on this machine."""
    prevent_sleep()
    try:
        state = ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
        assert _unsigned(state) == (_ES_CONTINUOUS | _ES_SYSTEM_REQUIRED)
    finally:
        allow_sleep()


@pytest.mark.skipif(sys.platform != "win32", reason="Win32 execution state API only exists on Windows")
def test_allow_sleep_actually_clears_the_real_windows_execution_state():
    prevent_sleep()
    allow_sleep()
    state = ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
    assert _unsigned(state) == _ES_CONTINUOUS  # ES_SYSTEM_REQUIRED bit cleared


def test_prevent_sleep_is_a_noop_on_non_windows_platforms():
    with patch("desktop.sleep_guard.sys.platform", "linux"):
        with patch("ctypes.windll", create=True) as mock_windll:
            prevent_sleep()
            mock_windll.kernel32.SetThreadExecutionState.assert_not_called()


def test_allow_sleep_is_a_noop_on_non_windows_platforms():
    with patch("desktop.sleep_guard.sys.platform", "darwin"):
        with patch("ctypes.windll", create=True) as mock_windll:
            allow_sleep()
            mock_windll.kernel32.SetThreadExecutionState.assert_not_called()


def test_prevent_sleep_swallows_a_failing_api_call_instead_of_raising():
    """Sleep prevention is best-effort — it must never be the reason a
    collection run crashes, even if the OS call itself fails somehow."""
    with patch("ctypes.windll.kernel32.SetThreadExecutionState", side_effect=OSError("boom")):
        prevent_sleep()  # must not raise


def test_allow_sleep_swallows_a_failing_api_call_instead_of_raising():
    with patch("ctypes.windll.kernel32.SetThreadExecutionState", side_effect=OSError("boom")):
        allow_sleep()  # must not raise

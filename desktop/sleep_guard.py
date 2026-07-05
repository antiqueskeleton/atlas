"""
Prevents Windows from sleeping while a long-running Atlas operation (a
Visibility collection) is in progress (#56) — a 1020-prompt collection went
to sleep mid-run and never finished, since Windows' idle-sleep timer has no
idea a background QThread is doing real work. This isn't hypothetical: the
v0.9.2 build process hit the identical problem mid-session (an ~8-hour sleep
interruption on what should have been a ~6-minute build), independent
real-world confirmation of the same failure mode.

Uses the same Win32 SetThreadExecutionState mechanism media players and
download managers use for this exact problem — no new pip dependency, just
ctypes calling directly into kernel32.dll. ES_CONTINUOUS makes the request
persist until explicitly released (or the process exits) rather than only
resetting the idle timer once, so a single prevent_sleep() call at the start
of a long operation is sufficient — no periodic re-calling needed, per
Microsoft's documented behavior for this flag combination.

Deliberately does NOT include ES_DISPLAY_REQUIRED — this only blocks sleep,
not the display turning off. A long collection plausibly runs in the
background while the user works on something else; forcing the screen to
stay lit was never asked for and would be an unwelcome side effect.

Windows-only (ctypes.windll doesn't exist elsewhere) and best-effort: on any
other platform, or if the call fails for any reason, both functions become a
silent no-op. Sleep prevention is a nice-to-have — it must never be the
reason a collection run crashes.
"""
import sys

_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


def prevent_sleep() -> None:
    """Tell Windows a long operation is in progress — do not idle-sleep."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(
            _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED
        )
    except Exception:
        pass


def allow_sleep() -> None:
    """Release the sleep-prevention request — restores normal idle behavior."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
    except Exception:
        pass

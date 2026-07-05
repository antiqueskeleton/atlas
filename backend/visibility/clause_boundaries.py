"""
Shared sentence-splitting and clause-boundary clamping for the rule-based
cue-detection modules (negation.py, recommendation.py). Extracted so both
modules follow the exact same, already-proven approach to one hard problem —
a cue's reach must not bleed across a clause boundary onto a different brand
named in the same comparative sentence — rather than each carrying its own
copy that could drift out of sync or repeat the same bugs independently.

"Not as reliable as Honda", "worse than Honda", "unlike Honda, Firman...":
a cue's window is clamped at the nearest comma/"than"/"as" rather than the
raw character window, so a cue aimed at one brand doesn't reach a different
brand on the other side of the comparison. This only ever shrinks a
zone — never grows it — so it can suppress false positives but not create
them.
"""
import re

SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')

BOUNDARY_RE = re.compile(r',|\bthan\b|\bas\b')


def clamp_forward(sent_lower: str, cue_end: int, zone_end: int) -> int:
    m = BOUNDARY_RE.search(sent_lower, cue_end, zone_end)
    return m.start() if m else zone_end


def clamp_backward(sent_lower: str, zone_start: int, cue_start: int) -> int:
    last_end = zone_start
    for m in BOUNDARY_RE.finditer(sent_lower, zone_start, cue_start):
        last_end = m.end()
    return last_end

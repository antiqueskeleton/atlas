"""
Lightweight, rule-based negative-context detection for brand mentions.

Kept deliberately simple and auditable (no ML/NLP dependency) — consistent
with the rest of the analytics pipeline: every classification here can be
traced back to a literal cue word within a fixed character window of the
brand mention, not an opaque model score.

Two cue categories, because negation direction matters:
  - Symmetric cues ("not", "lacks", "unreliable"...) can modify a brand
    mentioned just before OR after them — "Firman is unreliable" and
    "unreliable brands like Firman" both count.
  - Forward-only cues ("unlike", "instead of", "rather than") grammatically
    negate whatever comes right AFTER them, never before — "Unlike Honda,
    Firman..." must flag Honda, not Firman, which is praised in the same
    sentence.

Known limitations: this cannot resolve double negatives ("not a bad
choice" reads positive but would be flagged negative) and comparative
sentences with more than two brands can still misattribute. It catches
the common, high-value cases, not every case.
"""
import re

# Modify a brand mentioned on either side, within _WINDOW characters.
_SYMMETRIC_CUES = [
    "not", "isn't", "aren't", "doesn't", "don't", "won't", "wouldn't",
    "can't", "cannot", "never", "no longer", "avoid", "fails to",
    "failed to", "lacks", "lacking", "worse than", "less reliable",
    "less durable", "steer clear", "stay away", "wouldn't recommend",
    "not recommend", "disappointing", "unreliable", "struggles with",
    "problems with", "issues with", "complaints about", "poor", "inferior",
    "downside",
]

# Only negate a brand mentioned shortly AFTER the cue — never before.
_FORWARD_ONLY_CUES = ["unlike", "instead of", "rather than"]

_WINDOW = 25          # chars checked on each side for symmetric cues
_FORWARD_WINDOW = 35  # chars checked after a forward-only cue

# Pre-compiled once at import time. _cue_zones() runs per-sentence, per-response
# (tens of thousands of times on a large response set) — building/escaping a
# fresh pattern string per cue inside that loop instead of reusing a compiled
# Pattern turned into the dominant cost of startup analytics as the stored
# response count grew (profiled: 2.9M redundant re.escape()/compile calls on a
# ~3,500-response database, ~17s of an ~19s summarize_responses() call).
_SYMMETRIC_PATTERNS = [re.compile(r'\b' + re.escape(cue) + r'\b') for cue in _SYMMETRIC_CUES]
_FORWARD_ONLY_PATTERNS = [re.compile(r'\b' + re.escape(cue) + r'\b') for cue in _FORWARD_ONLY_CUES]

# Cheap pre-filter: a plain substring check is a strict superset of the precise
# \b-bounded patterns above (anything the precise patterns could match must
# contain one of these substrings), so if none of them appear at all, none of
# the 37 precise patterns can match either. Most sentences in a generator
# Q&A response contain zero negative-cue words — skipping straight to "no
# zones" for those avoids running all 37 compiled patterns against them.
_ALL_CUES = _SYMMETRIC_CUES + _FORWARD_ONLY_CUES

_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+')

# Clause-boundary tokens: comparative connectors that separate one entity
# from another within the same sentence ("not AS reliable AS Honda",
# "worse THAN Honda", "unlike Honda, Firman..."). A cue's reach is clamped
# at the nearest one of these rather than the raw character window, so a
# negation aimed at one brand doesn't bleed onto a different brand named
# on the other side of the comparison. This only ever shrinks a zone —
# never grows it — so it can suppress false positives but not create them.
_BOUNDARY_RE = re.compile(r',|\bthan\b|\bas\b')


def _clamp_forward(sent_lower: str, cue_end: int, zone_end: int) -> int:
    m = _BOUNDARY_RE.search(sent_lower, cue_end, zone_end)
    return m.start() if m else zone_end


def _clamp_backward(sent_lower: str, zone_start: int, cue_start: int) -> int:
    last_end = zone_start
    for m in _BOUNDARY_RE.finditer(sent_lower, zone_start, cue_start):
        last_end = m.end()
    return last_end


def _cue_zones(sent_lower: str) -> list[tuple[int, int]]:
    """Return (start, end) character ranges where a negative cue applies."""
    if not any(cue in sent_lower for cue in _ALL_CUES):
        return []

    zones = []

    for pattern in _SYMMETRIC_PATTERNS:
        for m in pattern.finditer(sent_lower):
            raw_start = max(0, m.start() - _WINDOW)
            raw_end = m.end() + _WINDOW
            start = _clamp_backward(sent_lower, raw_start, m.start())
            end = _clamp_forward(sent_lower, m.end(), raw_end)
            zones.append((start, end))

    for pattern in _FORWARD_ONLY_PATTERNS:
        for m in pattern.finditer(sent_lower):
            raw_end = m.end() + _FORWARD_WINDOW
            end = _clamp_forward(sent_lower, m.end(), raw_end)
            zones.append((m.end(), end))

    return zones


def detect_negative_brands(response_text: str,
                           flat_brand_terms: list[tuple[str, str]]) -> set[str]:
    """
    Return the set of brands (from flat_brand_terms) that appear in a
    negative context somewhere in response_text.

    flat_brand_terms is a list of (search_term_lowercase, brand_display_name)
    pairs, matching VisibilityAnalytics._flat_brand_terms.
    """
    if not response_text:
        return set()

    negative: set[str] = set()
    for sentence in _SENTENCE_SPLIT.split(response_text):
        sent_lower = sentence.lower()
        zones = _cue_zones(sent_lower)
        if not zones:
            continue

        for term, brand in flat_brand_terms:
            if brand in negative:
                continue  # already flagged from an earlier sentence
            idx = sent_lower.find(term)
            if idx < 0:
                continue
            term_end = idx + len(term)
            if any(idx < z_end and term_end > z_start for z_start, z_end in zones):
                negative.add(brand)

    return negative

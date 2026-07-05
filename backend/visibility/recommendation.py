"""
Lightweight, rule-based positive-recommendation detection for brand mentions
(#65) — distinguishes "Firman is one of several options AI listed" from
"I'd specifically recommend the Firman T07573." Same deliberately simple,
auditable, rule-based approach as negation.py (no ML/NLP dependency, every
classification traceable to a literal cue phrase within a fixed window of
the brand mention) and shares its clause-boundary clamping logic exactly —
see clause_boundaries.py.

This module only detects endorsement-style LANGUAGE near a brand; it does
NOT know about negation on its own. "I would not recommend the Firman"
contains the cue phrase "recommend the" and would be flagged here — the
caller (VisibilityAnalytics.summarize_responses) is responsible for
excluding brands that negation.py ALSO flags negative in the same response
before treating a detected brand as a genuine recommendation. This mirrors
how feature/channel association already excludes negatively-framed brands
(assoc_brand_names in visibility_analytics.py) — reusing an established
pattern rather than inventing recommendation-specific negation-awareness.

Known limitations, same class as negation.py: cannot resolve per-sentence
attribution across 3+ brands in one sentence, and the negation-suppression
above operates at the whole-response level (not per-sentence), so a brand
validly recommended in one sentence but also caught by an unrelated
negative cue elsewhere in the same response won't be credited. Catches the
common, high-value, high-precision cases, not every case.
"""
import re

from backend.visibility.clause_boundaries import SENTENCE_SPLIT, clamp_backward, clamp_forward

# Endorsement-style phrases a model uses when actively recommending a
# specific option, as opposed to merely listing it alongside others.
# Deliberately more specific than bare words like "recommend" alone would
# be too loose ("brands people recommend include...") — favors precision
# over recall, consistent with this whole pipeline's "defensible" goal:
# better to under-count real recommendations than to inflate the metric
# with generic descriptive text that never actually endorses anything.
_RECOMMENDATION_CUES = [
    "i recommend", "i'd recommend", "we recommend", "highly recommend",
    "would recommend", "recommend the", "recommend a", "recommend an",
    "my top pick", "top pick would be", "top pick is",
    "best choice would be", "best choice is", "the best choice",
    "best option would be", "best option is", "the best option",
    "i'd suggest", "would suggest", "i suggest",
    "your best bet is", "best bet would be", "the best bet",
    "go with the", "opt for the", "opt for a",
]

_WINDOW = 25  # chars checked on each side, same as negation.py's symmetric cues

# Pre-compiled once at import time, and pre-filtered via a substring check
# before running the precise \b-bounded patterns — same #53 lesson applied
# from the start here rather than needing a follow-up performance fix later.
_RECOMMENDATION_PATTERNS = [re.compile(r'\b' + re.escape(cue) + r'\b') for cue in _RECOMMENDATION_CUES]
_ALL_CUES = _RECOMMENDATION_CUES


def _cue_zones(sent_lower: str) -> list[tuple[int, int]]:
    """Return (start, end) character ranges where a recommendation cue applies."""
    if not any(cue in sent_lower for cue in _ALL_CUES):
        return []

    zones = []
    for pattern in _RECOMMENDATION_PATTERNS:
        for m in pattern.finditer(sent_lower):
            raw_start = max(0, m.start() - _WINDOW)
            raw_end = m.end() + _WINDOW
            start = clamp_backward(sent_lower, raw_start, m.start())
            end = clamp_forward(sent_lower, m.end(), raw_end)
            zones.append((start, end))

    return zones


def detect_recommended_brands(response_text: str,
                              flat_brand_terms: list[tuple[str, str]]) -> set[str]:
    """
    Return the set of brands (from flat_brand_terms) that appear in an
    endorsement/recommendation context somewhere in response_text.

    flat_brand_terms is a list of (search_term_lowercase, brand_display_name)
    pairs, matching VisibilityAnalytics._flat_brand_terms — same signature
    as negation.detect_negative_brands for a consistent call pattern.
    """
    if not response_text:
        return set()

    recommended: set[str] = set()
    for sentence in SENTENCE_SPLIT.split(response_text):
        sent_lower = sentence.lower()
        zones = _cue_zones(sent_lower)
        if not zones:
            continue

        for term, brand in flat_brand_terms:
            if brand in recommended:
                continue  # already flagged from an earlier sentence
            idx = sent_lower.find(term)
            if idx < 0:
                continue
            term_end = idx + len(term)
            if any(idx < z_end and term_end > z_start for z_start, z_end in zones):
                recommended.add(brand)

    return recommended

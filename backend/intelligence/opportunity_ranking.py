"""
Deterministic, evidence-based opportunity priority ranking.

get_all_opportunities() sorts by created_date DESC — a recency order, not a
priority order (the display number "#75" only ever meant "75th most recent
across all runs," never "75th most important"; confirmed by reading the real
code before building anything here). This module ranks by what's actually
present in the data instead.

Checked real opportunity evidence text from a production database before
designing this (78 real opportunities): most evidence is qualitative
("Multiple responses emphasize...", "Champion and Honda have thousands of
reviews...") — only a minority cite an exact count, almost always as
"X of Y responses" or "X of Y top picks" (e.g. "0 of 84 responses",
"appears in 6 of 6 camping/RV generator top picks"). A ranking that only
works for a handful of opportunities and silently no-ops for the rest isn't
useful, so this deliberately handles both cases rather than assuming every
opportunity cites a parseable count:

  1. Opportunities citing an explicit "X of Y" ratio are ranked first, by
     that ratio ascending (0/84 - the target brand is completely absent -
     ranks above 5/6, since a full absence is the strongest, most
     actionable kind of finding a report can make).
  2. Opportunities with no parseable count keep the existing recency order,
     appended after every ratio-backed opportunity.

Deliberately NOT an LLM re-ranking pass — per the user's explicit priority
on factual, simple, inspectable results: every ranking decision here traces
back to a literal number already present in the AI's own cited evidence,
not a second AI opinion about what matters.
"""
import re

_RATIO_PATTERN = re.compile(r'\b(\d+)\s+of\s+(\d+)\b', re.IGNORECASE)


def _extract_ratio(evidence: str) -> float | None:
    """First "X of Y" match in evidence, as X/Y — or None if absent."""
    if not evidence:
        return None
    m = _RATIO_PATTERN.search(evidence)
    if not m:
        return None
    numerator, denominator = int(m.group(1)), int(m.group(2))
    if denominator == 0:
        return None
    return numerator / denominator


def rank_opportunities(opp_rows: list[tuple]) -> list[tuple]:
    """
    opp_rows: (opportunity_id, title, evidence, description, status,
    created_date, ...) tuples, matching get_all_opportunities()'s shape —
    already in created_date DESC (recency) order on input.

    Returns the same rows, reordered: ratio-backed opportunities first
    (lowest X/Y ratio first), then everything else in its original
    (recency) order. Stable sort, so ties keep their recency order too.
    """
    def sort_key(indexed_row):
        original_index, row = indexed_row
        evidence = row[2] if len(row) > 2 else ""
        ratio = _extract_ratio(evidence)
        if ratio is not None:
            return (0, ratio, original_index)
        return (1, 0.0, original_index)

    indexed = list(enumerate(opp_rows))
    indexed.sort(key=sort_key)
    return [row for _, row in indexed]

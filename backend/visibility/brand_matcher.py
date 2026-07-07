"""
Single-pass multi-brand text matching via Aho-Corasick.

Every brand-mention lookup in this codebase used to loop over every tracked
brand's search term and run a separate substring scan per term, per response
(or per sentence, for negation/recommendation detection) — O(brands x text).
As the brand list and response count both grow toward 100k+ responses, that
becomes the dominant cost of every analytics pass. An Aho-Corasick automaton
finds every occurrence of every term in ONE pass over the text — O(text
length), independent of how many brands are tracked.

Matching semantics (#87): WORD-BOUNDARY matching, case handled by the
caller lowercasing text before it's passed in. The first version
deliberately preserved the prior plain-substring semantics, but real data
proved that wrong at the core: 'cat' matched inside "category" and
"indicates", 'wen' inside "went" — systematically inflating every count
for short-named brands (CAT was showing as the #2 brand partly on
substring hits). A hit now only counts when the characters on both sides
of the match are non-alphanumeric, with a plural/possessive allowance
(trailing "s" or "'s": "Hondas"/"Honda's" still count as Honda).
Consequence, by design: brand counts DROP after this lands — that is a
correction of previously-inflated numbers, not data loss.
"""
import ahocorasick


def _boundary_ok(text: str, start: int, end: int) -> bool:
    """True when [start:end) sits on word boundaries in `text`.
    Allows a trailing plural/possessive: "hondas" / "honda's" count."""
    if start > 0 and text[start - 1].isalnum():
        return False
    n = len(text)
    if end >= n or not text[end].isalnum():
        return True
    # Trailing "s" then a boundary → plural ("hondas")
    if text[end] in "sS" and (end + 1 >= n or not text[end + 1].isalnum()):
        return True
    return False


def text_contains_term(text_lower: str, term: str) -> bool:
    """
    Word-boundary containment check for ad-hoc single-term scans — the
    shared replacement for the raw `term in text` substring tests that
    previously lived in intelligence_service/home_page/intelligence_page
    and carried the same #87 inflation bug as the matcher.
    """
    start = text_lower.find(term)
    while start != -1:
        if _boundary_ok(text_lower, start, start + len(term)):
            return True
        start = text_lower.find(term, start + 1)
    return False


def resolve_target_brand(target_brand: str, known_brands) -> str:
    """
    Case-insensitively resolve a free-typed target-brand string (Settings'
    target-brand field is a plain QLineEdit with no validation against the
    Knowledge brand list) to whatever casing that brand actually has in
    known_brands. Every KPI/analytics lookup keys a dict by the brand's
    canonical casing (e.g. "Firman") and does an exact-match `.get(target,
    0)` against it — so typing "FIRMAN" or "firman" in Settings previously
    made every one of those lookups silently miss and report 0, even though
    brand-mention detection in response text is itself case-insensitive.
    """
    if not target_brand:
        return target_brand
    lowered = target_brand.lower()
    for brand in known_brands:
        if brand.lower() == lowered:
            return brand
    return target_brand


class BrandTermMatcher:
    def __init__(self, flat_brand_terms: list[tuple[str, str]]):
        self.flat_brand_terms = flat_brand_terms

        # A term string can map to more than one brand (rare, but the prior
        # per-term-loop implementation allowed it, so this must too).
        self._term_to_brands: dict[str, list[str]] = {}
        for term, brand in flat_brand_terms:
            self._term_to_brands.setdefault(term, []).append(brand)

        self._automaton = ahocorasick.Automaton()
        for term in self._term_to_brands:
            self._automaton.add_word(term, term)
        self._automaton.make_automaton()

    def find_brand_positions(self, text: str) -> dict[str, int]:
        """
        Earliest character position of each brand's first-matching term in
        `text` (word-boundary matches only — see module docstring, #87).
        """
        brand_first_pos: dict[str, int] = {}
        for end_idx, term in self._automaton.iter(text):
            start_idx = end_idx - len(term) + 1
            if not _boundary_ok(text, start_idx, end_idx + 1):
                continue
            for brand in self._term_to_brands[term]:
                if brand not in brand_first_pos or start_idx < brand_first_pos[brand]:
                    brand_first_pos[brand] = start_idx
        return brand_first_pos

    def find_all_brand_occurrences(self, text: str) -> list[tuple[int, int, str]]:
        """
        Every word-boundary (start, end, brand) occurrence in `text` — not
        just the earliest per brand.
        """
        occurrences: list[tuple[int, int, str]] = []
        for end_idx, term in self._automaton.iter(text):
            start_idx = end_idx - len(term) + 1
            if not _boundary_ok(text, start_idx, end_idx + 1):
                continue
            for brand in self._term_to_brands[term]:
                occurrences.append((start_idx, end_idx + 1, brand))
        return occurrences

    def find_first_term_occurrences(self, text: str) -> list[tuple[int, int, str]]:
        """
        The FIRST occurrence of each distinct term string in `text`, as
        (start, end, brand) — one entry per matching term, not per brand.

        This exists specifically to reproduce negation.py/recommendation.py's
        pre-Aho-Corasick behavior exactly: the old code looped "for term,
        brand in flat_brand_terms: idx = sent_lower.find(term)" — checking
        only each TERM's first occurrence, independently per term (so a brand
        with 2 alias terms got 2 independent first-occurrence checks, not one
        earliest-across-all-aliases check). Checking every occurrence instead
        (find_all_brand_occurrences) is arguably more thorough, but it also
        increases exposure to a known, pre-existing sentence-splitting
        limitation in long/complex responses (see negation.py's docstring) —
        confirmed on real production data to shift negative/recommended
        counts by a few percent per brand. Kept as an exact behavior match by
        deliberate choice, not an oversight.
        """
        first_by_term: dict[str, tuple[int, int]] = {}
        for end_idx, term in self._automaton.iter(text):
            start_idx = end_idx - len(term) + 1
            if term not in first_by_term and _boundary_ok(text, start_idx, end_idx + 1):
                first_by_term[term] = (start_idx, end_idx + 1)

        occurrences: list[tuple[int, int, str]] = []
        for term, (start, end) in first_by_term.items():
            for brand in self._term_to_brands[term]:
                occurrences.append((start, end, brand))
        return occurrences

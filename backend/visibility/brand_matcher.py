"""
Single-pass multi-brand text matching via Aho-Corasick.

Every brand-mention lookup in this codebase used to loop over every tracked
brand's search term and run a separate substring scan per term, per response
(or per sentence, for negation/recommendation detection) — O(brands x text).
As the brand list and response count both grow toward 100k+ responses, that
becomes the dominant cost of every analytics pass. An Aho-Corasick automaton
finds every occurrence of every term in ONE pass over the text — O(text
length), independent of how many brands are tracked.

Preserves the exact matching semantics of the code it replaces: plain
substring matching, no word boundaries, case handled by the caller
lowercasing text before it's passed in (matching the existing convention
throughout backend/visibility/). Verified byte-for-byte identical output
against the prior per-term-loop implementation on the real production
database before this replaced it.
"""
import ahocorasick


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
        `text`. Replaces the "for term, brand in flat_brand_terms: text.find
        (term)" loop in VisibilityAnalytics.summarize_responses().
        """
        brand_first_pos: dict[str, int] = {}
        for end_idx, term in self._automaton.iter(text):
            start_idx = end_idx - len(term) + 1
            for brand in self._term_to_brands[term]:
                if brand not in brand_first_pos or start_idx < brand_first_pos[brand]:
                    brand_first_pos[brand] = start_idx
        return brand_first_pos

    def find_all_brand_occurrences(self, text: str) -> list[tuple[int, int, str]]:
        """
        Every (start, end, brand) occurrence in `text` — not just the
        earliest per brand.
        """
        occurrences: list[tuple[int, int, str]] = []
        for end_idx, term in self._automaton.iter(text):
            start_idx = end_idx - len(term) + 1
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
            if term not in first_by_term:
                first_by_term[term] = (end_idx - len(term) + 1, end_idx + 1)

        occurrences: list[tuple[int, int, str]] = []
        for term, (start, end) in first_by_term.items():
            for brand in self._term_to_brands[term]:
                occurrences.append((start, end, brand))
        return occurrences

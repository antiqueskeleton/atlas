"""
Tests for BrandTermMatcher (backend/visibility/brand_matcher.py) — the
Aho-Corasick single-pass replacement for the per-term-loop brand matching
previously duplicated in visibility_analytics.py/negation.py/recommendation.py.

Must preserve the exact matching semantics of a plain substring loop: no
word boundaries, case handled by the caller lowercasing text first (matching
existing convention throughout backend/visibility/) — deliberately not
"smarter" than the code it replaces, just faster.
"""
from backend.visibility.brand_matcher import BrandTermMatcher, resolve_target_brand

_FLAT_TERMS = [
    ("firman", "Firman"),
    ("honda", "Honda"),
    ("generac", "Generac"),
    ("cat", "CAT"),
]


def test_find_brand_positions_finds_each_brand_once_at_earliest_occurrence():
    text = "firman is a budget option, but honda is more reliable than firman."
    matcher = BrandTermMatcher(_FLAT_TERMS)
    positions = matcher.find_brand_positions(text)

    assert set(positions) == {"Firman", "Honda"}
    assert positions["Firman"] == text.index("firman")  # first occurrence, not the second
    assert positions["Honda"] == text.index("honda")


def test_find_brand_positions_returns_empty_dict_for_no_matches():
    matcher = BrandTermMatcher(_FLAT_TERMS)
    assert matcher.find_brand_positions("no tracked brands mentioned here at all.") == {}


def test_multiple_alias_terms_for_the_same_brand_use_the_earliest_of_either():
    """A brand with 2+ alias terms must count once, at whichever alias
    occurs first — not double-counted, matching the prior per-term-loop
    behavior (brand_first_pos dict keyed by brand, not by term)."""
    flat_terms = [("firman", "Firman"), ("firman generators", "Firman"), ("honda", "Honda")]
    matcher = BrandTermMatcher(flat_terms)
    text = "firman generators are a good value; honda costs more."
    positions = matcher.find_brand_positions(text)

    assert positions["Firman"] == 0  # "firman" (inside "firman generators") matches at 0


def test_a_term_shared_by_two_different_brands_credits_both():
    """Rare but the prior implementation allowed a single term string to map
    to more than one brand (e.g. a shared alias) — both must be credited."""
    flat_terms = [("power co", "Brand A"), ("power co", "Brand B")]
    matcher = BrandTermMatcher(flat_terms)
    text = "we recommend power co for this budget."
    positions = matcher.find_brand_positions(text)

    assert positions == {"Brand A": text.index("power co"), "Brand B": text.index("power co")}


def test_find_all_brand_occurrences_returns_every_occurrence_not_just_first():
    text = "firman is affordable. firman also has decent warranty coverage."
    matcher = BrandTermMatcher(_FLAT_TERMS)
    occurrences = matcher.find_all_brand_occurrences(text)

    firman_occurrences = [o for o in occurrences if o[2] == "Firman"]
    assert len(firman_occurrences) == 2
    assert firman_occurrences[0][0] == text.index("firman")
    assert firman_occurrences[1][0] == text.rindex("firman")


def test_find_all_brand_occurrences_gives_correct_start_end_span():
    matcher = BrandTermMatcher(_FLAT_TERMS)
    text = "xx honda yy"
    occurrences = matcher.find_all_brand_occurrences(text)

    assert occurrences == [(3, 8, "Honda")]
    assert text[3:8] == "honda"


def test_find_first_term_occurrences_uses_only_the_first_occurrence_of_each_term():
    """
    Reproduces negation.py/recommendation.py's exact pre-Aho-Corasick
    behavior: "for term, brand in flat_brand_terms: sent.find(term)" checks
    only each term's FIRST occurrence, never a later repeat within the same
    sentence — deliberately kept this way after finding on real production
    data that checking every occurrence increases exposure to a known,
    already-documented sentence-splitting edge case (see negation.py).
    """
    text = "firman is affordable. firman also has decent warranty coverage."
    matcher = BrandTermMatcher(_FLAT_TERMS)
    occurrences = matcher.find_first_term_occurrences(text)

    firman_occurrences = [o for o in occurrences if o[2] == "Firman"]
    assert len(firman_occurrences) == 1
    assert firman_occurrences[0][0] == text.index("firman")  # the first one, not the second


def test_find_first_term_occurrences_still_finds_each_distinct_brand():
    matcher = BrandTermMatcher(_FLAT_TERMS)
    text = "firman is affordable, honda is more reliable."
    occurrences = matcher.find_first_term_occurrences(text)

    assert {b for _, _, b in occurrences} == {"Firman", "Honda"}


def test_word_boundary_matching_rejects_substring_hits():
    """
    #87: the original implementation deliberately preserved the prior
    plain-substring semantics ("cat" matched inside "category"), but real
    data proved that a core factual defect — every count for a short-named
    brand was inflated by substring hits ("category", "indicates", "went").
    Boundary matching is now the required behavior.
    """
    matcher = BrandTermMatcher(_FLAT_TERMS)
    assert "CAT" not in matcher.find_brand_positions("browse by category")
    assert "CAT" not in matcher.find_brand_positions("this indicates a problem")
    assert "CAT" in matcher.find_brand_positions("the cat rp12000e is solid")


def test_word_boundary_allows_plural_and_possessive():
    matcher = BrandTermMatcher([("honda", "Honda")])
    assert "Honda" in matcher.find_brand_positions("hondas are quiet")
    assert "Honda" in matcher.find_brand_positions("honda's eu2200i is the pick")
    assert "Honda" not in matcher.find_brand_positions("hondanet is a website")


def test_word_boundary_applies_to_all_three_query_methods():
    matcher = BrandTermMatcher(_FLAT_TERMS)
    text = "category pages went live"  # substring hits for CAT only via 'category'
    assert matcher.find_brand_positions(text) == {}
    assert matcher.find_all_brand_occurrences(text) == []
    assert matcher.find_first_term_occurrences(text) == []


def test_text_contains_term_boundary_semantics():
    """Shared helper for the ad-hoc single-term scans in intelligence/home
    pages — must match BrandTermMatcher's boundary rules exactly."""
    assert resolve_target_brand is not None  # module import sanity
    from backend.visibility.brand_matcher import text_contains_term
    assert text_contains_term("the cat rp12000e", "cat") is True
    assert text_contains_term("browse by category", "cat") is False
    assert text_contains_term("this indicates trouble", "cat") is False
    assert text_contains_term("hondas are quiet", "honda") is True
    assert text_contains_term("i went with generac", "wen") is False
    # Second occurrence valid even when the first is embedded
    assert text_contains_term("categories aside, the cat xq230 works", "cat") is True


# ── resolve_target_brand (#82 case-sensitivity fix) ─────────────────────────

def test_resolve_target_brand_matches_regardless_of_input_casing():
    known = ["Firman", "Honda", "Generac"]
    assert resolve_target_brand("FIRMAN", known) == "Firman"
    assert resolve_target_brand("firman", known) == "Firman"
    assert resolve_target_brand("FiRmAn", known) == "Firman"


def test_resolve_target_brand_returns_input_unchanged_when_already_correct_case():
    assert resolve_target_brand("Firman", ["Firman", "Honda"]) == "Firman"


def test_resolve_target_brand_falls_back_to_input_when_no_match_found():
    """A brand not in the known list (e.g. a typo) is passed through as-is
    rather than silently discarded — callers still get an in-band value to
    show/compare against, just with no canonical match to resolve to."""
    assert resolve_target_brand("NotTracked", ["Firman", "Honda"]) == "NotTracked"


def test_resolve_target_brand_passes_through_empty_string():
    assert resolve_target_brand("", ["Firman"]) == ""

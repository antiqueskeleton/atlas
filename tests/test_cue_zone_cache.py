"""
Tests for backend/visibility/cue_zone_cache.py — the persisted, per-response
cache of negation/recommendation cue-zones (#81). Brand-independent by
design (only depends on response text, which never changes once saved), so
it's safe to compute once and reuse forever, unlike caching brand-mention
results directly (which WOULD go stale if the brand list changes later).
"""
from backend.visibility.cue_zone_cache import (
    compute_cue_zone_cache, parse_cue_zone_cache, zones_for_sentence,
)
from backend.visibility.negation import _cue_zones as neg_zones, detect_negative_brands
from backend.visibility.recommendation import _cue_zones as rec_zones, detect_recommended_brands

_FLAT_TERMS = [("firman", "Firman"), ("honda", "Honda"), ("generac", "Generac")]


def test_compute_cue_zone_cache_is_valid_json_with_only_qualifying_sentences():
    text = "Firman is a great value. Honda is not as reliable. Generac costs more."
    cached = compute_cue_zone_cache(text, neg_zones)
    import json
    parsed = json.loads(cached)

    # Sentence 0 ("Firman is a great value.") has no negative cue -> absent.
    # Sentence 1 ("Honda is not as reliable.") has "not" -> present.
    assert "0" not in parsed
    assert "1" in parsed


def test_compute_cue_zone_cache_returns_empty_object_for_no_cues_anywhere():
    text = "Firman and Honda are both solid choices for home backup."
    cached = compute_cue_zone_cache(text, neg_zones)
    assert cached == "{}"


def test_zones_for_sentence_reads_back_the_same_zones_as_direct_computation():
    text = "Honda is not as reliable as Firman for this use case."
    cached = compute_cue_zone_cache(text, neg_zones)
    parsed = parse_cue_zone_cache(cached)

    from backend.visibility.clause_boundaries import SENTENCE_SPLIT
    sentences = SENTENCE_SPLIT.split(text)
    for i, sentence in enumerate(sentences):
        direct = neg_zones(sentence.lower())
        via_cache = zones_for_sentence(parsed, i)
        assert direct == via_cache


def test_parse_cue_zone_cache_handles_none_and_empty_string():
    assert parse_cue_zone_cache(None) == {}
    assert parse_cue_zone_cache("") == {}
    assert parse_cue_zone_cache("{}") == {}


def test_zones_for_sentence_returns_empty_list_for_missing_index():
    assert zones_for_sentence({}, 0) == []
    assert zones_for_sentence(parse_cue_zone_cache("{}"), 5) == []


def test_detect_negative_brands_gives_identical_result_with_or_without_cache():
    text = "Firman is not as reliable as Honda for daily use."
    cached = compute_cue_zone_cache(text, neg_zones)

    fresh = detect_negative_brands(text, _FLAT_TERMS)
    from_cache = detect_negative_brands(text, _FLAT_TERMS, cached)
    assert fresh == from_cache == {"Firman"}


def test_detect_recommended_brands_gives_identical_result_with_or_without_cache():
    text = "I'd recommend the Generac for this budget."
    cached = compute_cue_zone_cache(text, rec_zones)

    fresh = detect_recommended_brands(text, _FLAT_TERMS)
    from_cache = detect_recommended_brands(text, _FLAT_TERMS, cached)
    assert fresh == from_cache == {"Generac"}


def test_empty_cache_string_means_zero_zones_not_compute_fresh():
    """A response with genuinely zero cue zones caches as '{}' (falsy string
    content but not None) — passing it must NOT fall back to fresh
    computation, since that would defeat the whole point of caching."""
    text = "Firman is not as reliable as Honda."  # WOULD have a zone if computed fresh
    result = detect_negative_brands(text, _FLAT_TERMS, cached_zones_json="{}")
    assert result == set()  # cache says no zones -> trust the cache, don't recompute

"""
Tests for intelligence_service.py's classification/bucketing logic (#43) —
_classify_family() and _classify_visibility_responses(). This is the gate
that decides what data the entire Intelligence Engine sees; a bug here
silently skews every downstream briefing and opportunity list.

Rows use an explicit prompt_set (row[7]) that isn't "All Prompts" so
classification resolves without touching the real data/market_questions.csv —
keeps these tests hermetic regardless of what's in anyone's data directory.
"""
from backend.intelligence.intelligence_service import IntelligenceService


class _FakePM:
    active_provider_name = "fake"


def _service(target_brand="Firman"):
    return IntelligenceService(_FakePM(), target_brand=target_brand)


def row(id_, prompt, response, prompt_set):
    """Row shape: (id, run_id, provider, model, prompt, response, collected_at, prompt_set)"""
    return (id_, "r1", "openai", "model", prompt, response, "2026-07-01", prompt_set)


# ── _classify_family ──────────────────────────────────────────────────────────

def test_brand_perception_family_classified_as_brand():
    svc = _service()
    assert svc._classify_family("Firman Brand Perception") == "brand"


def test_generic_brand_awareness_terms_classify_as_brand_for_any_target():
    svc = _service(target_brand="Honda")
    # generic terms in _BRAND_TERMS shouldn't require the target brand's name
    assert svc._classify_family("Brand Awareness Study") == "brand"
    # dynamic "{target} brand" term should also work for whatever brand is active
    assert svc._classify_family("Honda Brand Deep Dive") == "brand"


def test_journey_terms_classify_as_journey():
    svc = _service()
    assert svc._classify_family("Channel Intelligence") == "journey"
    assert svc._classify_family("Customer Service Experience") == "journey"


def test_brand_check_takes_priority_over_journey_for_overlapping_term():
    """
    "brand comparison" previously appeared in BOTH _BRAND_TERMS and
    _JOURNEY_TERMS — a real regression introduced when _BRAND_TERMS was
    broadened from just "firman brand" to generic terms (2026-07-02 session),
    without checking for overlap against the pre-existing journey list. Since
    brand classification runs first, the journey entry was silently dead code.
    Fixed by removing it from _JOURNEY_TERMS — "Brand Comparison" is more
    naturally a brand-positioning topic than a buying-journey topic, and
    _JOURNEY_TERMS still has "comparison guide" for journey-style comparisons.
    This test pins that resolution so it can't silently drift back.
    """
    svc = _service()
    assert svc._classify_family("Brand Comparison Guide") == "brand"


def test_persona_terms_classify_as_persona():
    svc = _service()
    assert svc._classify_family("Generator for First Time Buyers") == "persona"
    assert svc._classify_family("Best Emergency Preparedness") == "persona"


def test_unmatched_family_defaults_to_product():
    svc = _service()
    assert svc._classify_family("Random Unrelated Family Name") == "product"
    assert svc._classify_family("") == "product"


def test_classification_is_case_insensitive():
    svc = _service()
    assert svc._classify_family("CHANNEL INTELLIGENCE") == "journey"
    assert svc._classify_family("channel intelligence") == "journey"


# ── _classify_visibility_responses: bucketing ─────────────────────────────────

def test_responses_land_in_the_correct_bucket():
    svc = _service()
    rows = [
        row(1, "q1", "a1", "Channel Intelligence"),          # journey
        row(2, "q2", "a2", "Best Emergency Preparedness"),   # persona
        row(3, "q3", "a3", "Firman Brand Perception"),       # brand
        row(4, "q4", "a4", "Random Product Question"),       # product (default)
    ]
    buckets = svc._classify_visibility_responses(rows)
    assert buckets["Buying Journey"] == [("q1", "a1")]
    assert buckets["Consumer Personas"] == [("q2", "a2")]
    assert buckets["Brand Intelligence"] == [("q3", "a3")]
    assert buckets["Product Intelligence"] == [("q4", "a4")]


def test_all_prompts_family_falls_through_to_csv_lookup_and_defaults_product():
    """
    prompt_set == "All Prompts" is explicitly treated as "not a real family
    name" — classification falls back to a CSV lookup which won't find an
    unknown prompt, so it defaults to product. This is intentional: "All
    Prompts" is a collection-run label, not a real family a response belongs to.
    """
    svc = _service()
    rows = [row(1, "some prompt never in the CSV", "answer", "All Prompts")]
    buckets = svc._classify_visibility_responses(rows)
    assert buckets["Product Intelligence"] == [("some prompt never in the CSV", "answer")]


# ── _classify_visibility_responses: deduplication ─────────────────────────────

def test_duplicate_prompt_text_keeps_only_the_first_occurrence():
    """
    list_responses() returns rows in DESC order (most recent first), so the
    FIRST occurrence of a given prompt text encountered here is the most
    recent collection of it — later (older) duplicates must be dropped.
    """
    svc = _service()
    rows = [
        row(1, "What generator should I buy?", "newest answer", "Random Family"),
        row(2, "What generator should I buy?", "older answer", "Random Family"),
    ]
    buckets = svc._classify_visibility_responses(rows)
    assert buckets["Product Intelligence"] == [("What generator should I buy?", "newest answer")]


def test_same_prompt_text_different_families_still_dedupes_on_first_seen():
    svc = _service()
    rows = [
        row(1, "shared prompt", "answer A", "Channel Intelligence"),  # journey, seen first
        row(2, "shared prompt", "answer B", "Firman Brand Perception"),  # brand, but dropped
    ]
    buckets = svc._classify_visibility_responses(rows)
    assert buckets["Buying Journey"] == [("shared prompt", "answer A")]
    assert buckets["Brand Intelligence"] == []


# ── _classify_visibility_responses: 25-per-bucket cap ─────────────────────────

def test_bucket_is_capped_at_25_responses():
    svc = _service()
    rows = [
        row(i, f"unique prompt {i}", f"answer {i}", "Random Product Family")
        for i in range(40)
    ]
    buckets = svc._classify_visibility_responses(rows)
    assert len(buckets["Product Intelligence"]) == 25


def test_cap_keeps_the_first_25_in_input_order():
    """
    Input order is assumed DESC-by-date (most recent first) per list_responses()
    — so capping at the first 25 means keeping the 25 MOST RECENT, not an
    arbitrary or random 25. Worth being explicit about, since this is exactly
    the recency-bias behavior flagged in #43 as needing user-visible disclosure.
    """
    svc = _service()
    rows = [
        row(i, f"unique prompt {i}", f"answer {i}", "Random Product Family")
        for i in range(30)
    ]
    buckets = svc._classify_visibility_responses(rows)
    kept_prompts = [p for p, _ in buckets["Product Intelligence"]]
    assert kept_prompts == [f"unique prompt {i}" for i in range(25)]

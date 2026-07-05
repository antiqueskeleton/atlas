"""
Tests for backend/visibility/visibility_analytics.py — the core scoring math
behind every Visibility table, Trends chart, and PDF/Excel export.

Builds VisibilityAnalytics with __new__() and hand-set attributes rather than
going through __init__(), so these tests don't depend on the live database or
data/*.csv files — they're isolated and reproducible regardless of what's
been collected in anyone's dev environment.

Response row shape mirrors visibility_repository rows:
  (id, run_id, provider, model, prompt, response, collected_at, family_name)
"""
import pytest

from backend.visibility.visibility_analytics import VisibilityAnalytics


def make_analytics(target_brand="Firman"):
    a = VisibilityAnalytics.__new__(VisibilityAnalytics)
    a.target_brand = target_brand
    a.brands = ["Firman", "Honda", "Generac"]
    a.brand_terms = {"Firman": ["firman"], "Honda": ["honda"], "Generac": ["generac"]}
    a.features = ["Dual Fuel", "Electric Start"]
    a.channels = [("Amazon", ["amazon"], "retail"), ("YouTube", ["youtube"], "content")]
    a._flat_brand_terms = [("firman", "Firman"), ("honda", "Honda"), ("generac", "Generac")]
    a._feature_set = [(f, f.lower()) for f in a.features]
    return a


def row(id_, provider, response, family="fam1"):
    return (id_, "r1", provider, "model", f"q{id_}", response, "2026-07-01", family)


# ── Mention counting ─────────────────────────────────────────────────────────

def test_brand_counted_once_per_response_even_with_multiple_mentions():
    a = make_analytics()
    responses = [row(1, "openai", "Firman is great. I'd pick Firman over Honda.")]
    result = a.summarize_responses(responses)
    assert result["brand_counts"]["Firman"] == 1


def test_visibility_score_is_percentage_of_responses_mentioning_target():
    a = make_analytics()
    responses = [
        row(1, "openai", "Firman is a solid choice."),
        row(2, "openai", "Honda is well known for reliability."),
        row(3, "anthropic", "Generac dominates the home standby market."),
        row(4, "anthropic", "Firman and Generac both make portables."),
    ]
    result = a.summarize_responses(responses)
    assert result["total_responses"] == 4
    assert result["brand_counts"]["Firman"] == 2
    assert result["target_visibility_score"] == 50.0


def test_zero_responses_does_not_divide_by_zero():
    a = make_analytics()
    result = a.summarize_responses([])
    assert result["total_responses"] == 0
    assert result["target_visibility_score"] == 0


def test_total_tracked_brands_counts_all_tracked_brands_not_just_mentioned_ones():
    """
    #48: Mention Rank denominator was previously len(brand_counts) — only
    brands with ≥1 mention — which understated the tracked competitive set
    (e.g. 35 shown when 95 brands were actually tracked). total_tracked_brands
    must reflect the FULL tracked list regardless of how many responses were
    analyzed or how many brands actually appear in them.
    """
    a = make_analytics()  # 3 tracked brands: Firman, Honda, Generac
    # Only Firman is ever mentioned — Honda and Generac appear zero times.
    responses = [row(1, "openai", "Firman is a solid choice for home backup.")]
    result = a.summarize_responses(responses)
    assert len(result["brand_counts"]) == 1  # only Firman has a mention
    assert result["total_tracked_brands"] == 3  # but all 3 tracked brands count


# ── Position / first-mention share ────────────────────────────────────────────

def test_first_mentioned_brand_gets_first_mention_credit():
    a = make_analytics()
    responses = [row(1, "openai", "Honda is reliable. Firman is affordable.")]
    result = a.summarize_responses(responses)
    assert result["first_mentioned_brands"]["Honda"] == 1
    assert "Firman" not in result["first_mentioned_brands"]


def test_brand_position_counts_track_mention_order():
    a = make_analytics()
    responses = [row(1, "openai", "Generac leads, then Honda, then Firman.")]
    result = a.summarize_responses(responses)
    assert result["brand_position_counts"][1]["Generac"] == 1
    assert result["brand_position_counts"][2]["Honda"] == 1
    assert result["brand_position_counts"][3]["Firman"] == 1


# ── Negative-mention detection (#26) ──────────────────────────────────────────

def test_negative_mention_excluded_from_feature_association():
    a = make_analytics()
    responses = [row(
        1, "openai",
        "Honda includes electric start, unlike Firman which requires a pull cord.",
    )]
    result = a.summarize_responses(responses)
    # Firman was mentioned but in a losing comparison — should not be credited
    # with the Electric Start association it was explicitly denied.
    assert "Firman" not in result["feature_brand_counts"].get("Electric Start", {})
    assert result["feature_brand_counts"]["Electric Start"]["Honda"] == 1
    assert result["negative_brand_counts"]["Firman"] == 1


def test_negative_rate_is_relative_to_that_brands_own_mentions():
    a = make_analytics()
    responses = [
        row(1, "openai", "Firman is a great value pick."),
        row(2, "openai", "Firman is not as reliable as Honda for home backup."),
    ]
    result = a.summarize_responses(responses)
    # Firman: 2 mentions, 1 negative -> 50%, not 25% (which would be vs total responses)
    assert result["brand_counts"]["Firman"] == 2
    assert result["negative_brand_counts"]["Firman"] == 1
    assert result["brand_negative_rate"]["Firman"] == 50.0


def test_no_negative_context_yields_zero_negative_rate():
    a = make_analytics()
    responses = [row(1, "openai", "Firman and Generac are both solid choices.")]
    result = a.summarize_responses(responses)
    assert result["negative_brand_counts"] == {}
    assert result["brand_negative_rate"]["Firman"] == 0


# ── Recommendation detection (#65) ────────────────────────────────────────────

def test_recommended_brand_counted_separately_from_plain_mention():
    a = make_analytics()
    responses = [
        row(1, "openai", "Generac and Firman are both solid choices."),  # mention only
        row(2, "openai", "For home backup, I recommend the Firman."),   # genuine recommendation
    ]
    result = a.summarize_responses(responses)
    assert result["brand_counts"]["Firman"] == 2       # mentioned in both
    assert result["recommended_brand_counts"]["Firman"] == 1  # recommended in only one
    assert "Generac" not in result["recommended_brand_counts"]


def test_recommendation_rate_is_relative_to_that_brands_own_mentions():
    a = make_analytics()
    responses = [
        row(1, "openai", "Firman is a great value pick."),        # mention, no endorsement
        row(2, "openai", "I recommend the Firman for reliability."),  # mention + endorsement
    ]
    result = a.summarize_responses(responses)
    # Firman: 2 mentions, 1 recommendation -> 50%, not 25% (vs total responses)
    assert result["brand_counts"]["Firman"] == 2
    assert result["recommended_brand_counts"]["Firman"] == 1
    assert result["brand_recommendation_rate"]["Firman"] == 50.0


def test_target_recommendation_rate_is_percent_of_all_responses():
    a = make_analytics()
    responses = [
        row(1, "openai", "I recommend the Firman for home backup."),
        row(2, "openai", "Honda is well known for reliability."),
    ]
    result = a.summarize_responses(responses)
    assert result["target_recommendation_rate"] == 50.0


def test_no_endorsement_language_yields_zero_recommendation_rate():
    a = make_analytics()
    responses = [row(1, "openai", "Firman and Generac are both solid choices.")]
    result = a.summarize_responses(responses)
    assert result["recommended_brand_counts"] == {}
    assert result["brand_recommendation_rate"]["Firman"] == 0


def test_negated_recommendation_phrase_is_not_credited_as_a_recommendation():
    """The core #65 correctness requirement: recommendation.py alone would
    flag Firman here (it matches the literal cue phrase "recommend the"),
    but visibility_analytics must exclude it since negation.py ALSO flags
    Firman negative in the same response ("not... recommend")."""
    a = make_analytics()
    responses = [row(1, "openai", "I would not recommend the Firman for whole-home backup.")]
    result = a.summarize_responses(responses)
    assert result["brand_counts"]["Firman"] == 1
    assert result["negative_brand_counts"]["Firman"] == 1
    assert "Firman" not in result["recommended_brand_counts"]
    assert result["brand_recommendation_rate"]["Firman"] == 0


def test_first_recommended_position_differs_from_first_mentioned_position():
    """A brand can be mentioned first without being the first one actually
    recommended — first_recommended_brands must track that distinctly from
    the existing first_mentioned_brands."""
    a = make_analytics()
    responses = [row(
        1, "openai",
        "Honda is a well-known name, but I'd recommend the Firman for better value.",
    )]
    result = a.summarize_responses(responses)
    assert result["first_mentioned_brands"]["Honda"] == 1       # mentioned first
    assert "Honda" not in result.get("first_recommended_brands", {})
    assert result["first_recommended_brands"]["Firman"] == 1    # recommended first (and only)


# ── Channel co-occurrence / gap math ──────────────────────────────────────────

def test_channel_gap_only_reported_when_competitor_leads():
    a = make_analytics()
    responses = [
        row(1, "openai", "Generac is widely reviewed on YouTube."),
        row(2, "openai", "Generac has strong YouTube presence too."),
        row(3, "openai", "Firman also has a YouTube channel."),
    ]
    result = a.summarize_responses(responses)
    gap = next((g for g in result["target_channel_gap"] if g["channel"] == "YouTube"), None)
    assert gap is not None
    assert gap["target_count"] == 1
    assert gap["top_competitor"] == "Generac"
    assert gap["top_competitor_count"] == 2


def test_no_channel_gap_when_target_brand_leads():
    a = make_analytics()
    responses = [
        row(1, "openai", "Firman is popular on Amazon."),
        row(2, "openai", "Firman also sells well on Amazon."),
        row(3, "openai", "Honda has a small Amazon presence."),
    ]
    result = a.summarize_responses(responses)
    gap = next((g for g in result["target_channel_gap"] if g["channel"] == "Amazon"), None)
    assert gap is None


def test_channel_association_excludes_negatively_mentioned_brands():
    a = make_analytics()
    responses = [row(
        1, "openai",
        "Unlike Firman, Generac has a strong presence on Amazon.",
    )]
    result = a.summarize_responses(responses)
    # Firman was the one denied the Amazon association ("unlike Firman")
    assert "Firman" not in result["channel_brand_counts"].get("Amazon", {})
    assert result["channel_brand_counts"]["Amazon"]["Generac"] == 1


# ── detect_mentioned_brands (#68 Raw Data "Brands Mentioned" column) ────────────

def test_detect_mentioned_brands_finds_all_tracked_brands_in_text():
    a = make_analytics()
    assert a.detect_mentioned_brands("Firman and Honda are both solid choices.") == \
        ["Firman", "Honda"]


def test_detect_mentioned_brands_is_case_insensitive():
    a = make_analytics()
    assert a.detect_mentioned_brands("FIRMAN is a great option.") == ["Firman"]


def test_detect_mentioned_brands_returns_empty_list_when_none_mentioned():
    a = make_analytics()
    assert a.detect_mentioned_brands("Generators are useful during outages.") == []


def test_detect_mentioned_brands_counts_each_brand_once_even_with_repeats():
    a = make_analytics()
    assert a.detect_mentioned_brands("Firman is great. I'd pick Firman again.") == ["Firman"]

"""
Tests for backend/visibility/recommendation.py (#65) — distinguishes actively
recommending a brand from merely mentioning it alongside others. Mirrors
test_negation.py's structure since the module shares the same clause-boundary
clamping and cue-window approach.
"""
from backend.visibility.recommendation import detect_recommended_brands

_FLAT_TERMS = [("firman", "Firman"), ("honda", "Honda"), ("generac", "Generac")]


def test_direct_recommendation_flags_the_recommended_brand():
    text = "For home backup, I recommend the Firman T07573."
    assert detect_recommended_brands(text, _FLAT_TERMS) == {"Firman"}


def test_recommendation_cue_after_the_brand_name():
    text = "The Generac GP3500iO would be the best choice for camping trips."
    assert detect_recommended_brands(text, _FLAT_TERMS) == {"Generac"}


def test_plain_co_mention_is_not_a_recommendation():
    text = "For home backup power, Generac and Firman are both solid choices."
    assert detect_recommended_brands(text, _FLAT_TERMS) == set()


def test_comparative_sentence_does_not_credit_the_other_brand():
    text = "Compared to Honda, I recommend the Firman for better value."
    assert detect_recommended_brands(text, _FLAT_TERMS) == {"Firman"}


def test_cue_does_not_leak_past_a_clause_boundary_the_other_direction():
    text = "Honda offers quiet operation, but I'd recommend the Generac for price."
    assert detect_recommended_brands(text, _FLAT_TERMS) == {"Generac"}


def test_split_recommendations_across_two_sentences_credits_both():
    text = "I recommend the Firman for value. For quiet operation, I'd recommend the Honda."
    assert detect_recommended_brands(text, _FLAT_TERMS) == {"Firman", "Honda"}


def test_not_recommend_still_matches_the_cue_phrase_itself():
    """recommendation.py only detects endorsement LANGUAGE — it has no
    negation-awareness of its own. "I would not recommend the Firman"
    contains the literal cue phrase "recommend the" and IS flagged here;
    suppressing this false positive is the caller's job (combine with
    negation.detect_negative_brands and exclude the overlap), covered in
    tests/test_visibility_analytics.py, not this module in isolation."""
    text = "I would not recommend the Firman for whole-home backup."
    assert detect_recommended_brands(text, _FLAT_TERMS) == {"Firman"}


def test_empty_text_returns_empty_set():
    assert detect_recommended_brands("", _FLAT_TERMS) == set()


def test_multi_sentence_response_flags_brand_if_any_sentence_recommends_it():
    text = (
        "Firman is a popular choice for portable power. "
        "For most homeowners, I'd recommend the Firman over pricier alternatives."
    )
    assert "Firman" in detect_recommended_brands(text, _FLAT_TERMS)

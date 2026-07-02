"""
Tests for backend/visibility/negation.py — negative-context brand detection.

These cases are drawn directly from real ambiguous constructions found in
AI-generated brand comparisons: symmetric negation ("X lacks Y"), forward-only
comparatives ("unlike X, Y..."), and clause-boundary attribution in sentences
naming two brands ("X is not as reliable as Y" must flag X, not Y).
"""
from backend.visibility.negation import detect_negative_brands

_FLAT_TERMS = [("firman", "Firman"), ("honda", "Honda"), ("generac", "Generac")]


def test_direct_negation_flags_the_negated_brand():
    text = "Firman is NOT as reliable as Honda for home backup."
    assert detect_negative_brands(text, _FLAT_TERMS) == {"Firman"}


def test_forward_only_cue_flags_only_the_brand_right_after_it():
    text = "Unlike Honda, Firman offers dual fuel at a lower price point."
    assert detect_negative_brands(text, _FLAT_TERMS) == {"Honda"}


def test_forward_only_cue_does_not_leak_past_the_clause_boundary():
    text = "Honda includes electric start, unlike Firman which requires a pull cord."
    assert detect_negative_brands(text, _FLAT_TERMS) == {"Firman"}


def test_plain_co_mention_is_not_negative():
    text = "For home backup power, Generac and Firman are both solid choices."
    assert detect_negative_brands(text, _FLAT_TERMS) == set()


def test_split_preferences_across_brands_is_not_negative():
    text = "Many reviewers prefer Firman for value and Honda for reliability."
    assert detect_negative_brands(text, _FLAT_TERMS) == set()


def test_lacks_cue_does_not_bleed_onto_a_second_brand_in_the_same_sentence():
    text = "Firman lacks the industrial certifications that Generac has."
    assert detect_negative_brands(text, _FLAT_TERMS) == {"Firman"}


def test_symmetric_cue_after_the_brand_name():
    text = "Generac is the industry leader, but Firman struggles with brand recognition."
    assert detect_negative_brands(text, _FLAT_TERMS) == {"Firman"}


def test_empty_text_returns_empty_set():
    assert detect_negative_brands("", _FLAT_TERMS) == set()


def test_multi_sentence_response_flags_brand_negative_if_any_sentence_is():
    text = (
        "Firman is a popular choice for portable power. "
        "However, unlike Generac, Firman doesn't offer a whole-home standby option."
    )
    assert "Firman" in detect_negative_brands(text, _FLAT_TERMS)

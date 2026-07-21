"""
Model-level mentions (#66) + spec-contradiction detection (R4b) — pure
rule-based logic over catalog records; the H08051 'quiet inverter'
hallucination is the pinned scenario.
"""
from backend.catalog.model_mentions import (
    detect_spec_contradictions, find_model_mentions, scan_responses,
)

_H08051 = {"model": "H08051", "generator_type": "Dual Fuel",
           "fuel_types": ["Gasoline", "Liquified Petroleum Gas"]}
_W03083 = {"model": "W03083", "generator_type": "Inverter",
           "fuel_types": ["Gasoline"]}


def test_find_model_mentions_word_boundary_and_case():
    models = ["H08051", "W03083"]
    assert find_model_mentions("The Firman h08051 is solid.", models) == {"H08051"}
    assert find_model_mentions("SKU XH080511 is unrelated.", models) == set()
    assert find_model_mentions("no models here", models) == set()


def test_inverter_claim_on_synchronous_model_is_flagged():
    """The real hallucination: 'Best Quiet Tri-Fuel Generator
    (Inverter-Style): Firman H08051'."""
    text = ("Best Quiet Tri-Fuel Generator: the Firman H08051 is an "
            "inverter-style unit at ~72 dB. It is a great choice.")
    found = detect_spec_contradictions(text, _H08051)
    claims = {f["claim"] for f in found}
    assert claims == {"inverter", "tri-fuel"}          # both false claims caught
    assert all(f["model"] == "H08051" for f in found)
    assert any("not an inverter" in f["truth"] for f in found)


def test_true_claims_are_not_flagged():
    assert detect_spec_contradictions(
        "The Firman H08051 is a dual fuel generator.", _H08051) == []
    assert detect_spec_contradictions(
        "The W03083 inverter generator is quiet.", _W03083) == []


def test_claim_in_a_sentence_not_naming_the_model_is_ignored():
    text = ("The Firman H08051 is popular. Meanwhile inverter generators "
            "from Honda are quieter.")
    assert detect_spec_contradictions(text, _H08051) == []


def test_dual_fuel_claim_on_gas_only_model_is_flagged():
    found = detect_spec_contradictions(
        "The W03083 is a dual fuel inverter.", _W03083)
    assert {f["claim"] for f in found} == {"dual-fuel"}


def test_scan_responses_rolls_up_per_model_with_zero_rows():
    responses = [
        (1, "r", "OpenAI", "gpt", "q", "The H08051 is an inverter.", "", ""),
        (2, "r", "Gemini", "g", "q", "I like the h08051 dual fuel.", "", ""),
        (3, "r", "Grok", "g", "q", "No models named here.", "", ""),
    ]
    out = scan_responses(responses, [_H08051, _W03083])
    assert out["H08051"]["mentions"] == 2
    assert len(out["H08051"]["contradictions"]) == 1
    assert out["H08051"]["contradictions"][0]["provider"] == "OpenAI"
    assert out["W03083"] == {"mentions": 0, "contradictions": []}   # visible zero

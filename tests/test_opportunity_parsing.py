"""
Tests for _parse_opportunities() robustness (#40) — regex-based parsing of
LLM output is inherently fragile; these tests characterize what format
deviations it tolerates and confirm nothing gets silently discarded.
"""
from backend.intelligence.intelligence_service import IntelligenceService

_parse = IntelligenceService._parse_opportunities


def test_well_formed_single_opportunity_parses_fully():
    text = (
        "OPPORTUNITY [1]: Close the review gap on Amazon\n"
        "EVIDENCE: 3 of 12 responses cited Generac's review count\n"
        "ACTION: Enroll in Amazon Vine\n"
        "TACTICS: Automate Seller Central Request-a-Review; seed 2 YouTube reviewers\n"
    )
    result = _parse(text)
    assert len(result) == 1
    assert result[0]["title"] == "Close the review gap on Amazon"
    assert result[0]["evidence"] == "3 of 12 responses cited Generac's review count"
    assert "Enroll in Amazon Vine" in result[0]["description"]
    assert "Automate Seller Central" in result[0]["description"]


def test_multiple_opportunities_all_parse():
    text = (
        "OPPORTUNITY [1]: First gap\n"
        "EVIDENCE: evidence one\n"
        "ACTION: action one\n"
        "TACTICS: tactic one\n"
        "\n"
        "OPPORTUNITY [2]: Second gap\n"
        "EVIDENCE: evidence two\n"
        "ACTION: action two\n"
        "TACTICS: tactic two\n"
    )
    result = _parse(text)
    assert len(result) == 2
    assert result[0]["title"] == "First gap"
    assert result[1]["title"] == "Second gap"


def test_missing_tactics_still_parses_title_evidence_action():
    text = (
        "OPPORTUNITY [1]: A gap with no tactics line\n"
        "EVIDENCE: some evidence\n"
        "ACTION: some action\n"
    )
    result = _parse(text)
    assert len(result) == 1
    assert result[0]["description"] == "some action"


def test_missing_opportunity_number_still_parses():
    """A provider that drops the [N] numbering entirely shouldn't lose the opportunity."""
    text = (
        "OPPORTUNITY: A gap with no number at all\n"
        "EVIDENCE: some evidence\n"
        "ACTION: some action\n"
        "TACTICS: some tactic\n"
    )
    result = _parse(text)
    assert len(result) == 1
    assert result[0]["title"] == "A gap with no number at all"


def test_markdown_bold_title_is_cleaned():
    text = (
        "OPPORTUNITY [1]: **Bold wrapped title**\n"
        "EVIDENCE: some evidence\n"
        "ACTION: some action\n"
        "TACTICS: some tactic\n"
    )
    result = _parse(text)
    assert len(result) == 1
    assert result[0]["title"] == "Bold wrapped title"
    assert "*" not in result[0]["title"]


def test_completely_malformed_text_falls_back_to_one_visible_card():
    """
    If the LLM produces real content but it doesn't match the expected format
    at all, the raw text must still surface as one card — not silently vanish
    into an empty opportunities list with no explanation to the user.
    """
    text = "Here are some thoughts on Firman's market position without using the requested format."
    result = _parse(text)
    assert len(result) == 1
    assert "Could not parse" in result[0]["title"]
    assert text in result[0]["description"]


def test_empty_text_returns_empty_list_not_a_fallback_card():
    """An empty/blank response is a different situation than malformed content —
    it shouldn't spawn a confusing 'could not parse' card for nothing."""
    assert _parse("") == []
    assert _parse("   \n  ") == []


def test_api_failure_marker_from_42_still_parses_as_a_real_card():
    """
    Confirms the #42 error-handling fallback format (a pre-formatted
    OPPORTUNITY block) is itself parseable by this function — the two
    fixes are meant to compose, not conflict.
    """
    text = (
        "OPPORTUNITY [1]: Opportunity generation failed\n"
        "EVIDENCE: fake request failed: rate limit exceeded\n"
        "ACTION: Run Intelligence Analysis again\n"
        "TACTICS: If this persists, check the API key and provider status in Settings"
    )
    result = _parse(text)
    assert len(result) == 1
    assert "failed" in result[0]["title"].lower()

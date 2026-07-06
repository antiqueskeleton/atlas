"""
Tests for backend/reports/briefing_sections.py (#81 continuation).

The multi-section sample below is drawn directly from a real stored
executive_briefing value (7 sections, confirmed by direct query) rather
than an invented example.
"""
from backend.reports.briefing_sections import split_briefing_sections

_REAL_BRIEFING = (
    "VISIBILITY SNAPSHOT  \n"
    "Firman appeared in 12 of 84 responses (14%), ranking #16 out of 39 brands tracked.\n\n"
    "WHAT AI MODELS SAY ABOUT FIRMAN  \n"
    "Firman is mentioned primarily as a value-oriented brand in the portable generator market.\n\n"
    "SENTIMENT  \n"
    "Out of Firman's 12 mentions, 4 were negative or unfavorable.\n\n"
    "KEY CONSUMER SEGMENTS  \n"
    '1. Budget-conscious buyers seeking "best under $500" or affordable generators.\n\n'
    "BUYING JOURNEY INSIGHTS  \n"
    "AI models direct consumers to consult expert reviews and comparison guides.\n\n"
    "GAPS AND RISKS  \n"
    "- Portfolio gap - Firman is not mentioned in the home standby category.\n\n"
    "RECOMMENDED ACTIONS  \n"
    "- Portfolio gap (home standby): No marketing tactic applies."
)


def test_splits_all_seven_real_sections_correctly():
    sections = split_briefing_sections(_REAL_BRIEFING)
    assert len(sections) == 7
    headers = [h for h, _ in sections]
    assert headers == [
        "VISIBILITY SNAPSHOT",
        "WHAT AI MODELS SAY ABOUT FIRMAN",
        "SENTIMENT",
        "KEY CONSUMER SEGMENTS",
        "BUYING JOURNEY INSIGHTS",
        "GAPS AND RISKS",
        "RECOMMENDED ACTIONS",
    ]


def test_header_and_body_are_stripped_of_whitespace():
    sections = split_briefing_sections(_REAL_BRIEFING)
    header, body = sections[0]
    assert header == "VISIBILITY SNAPSHOT"  # trailing spaces from the raw text stripped
    assert body.startswith("Firman appeared in 12 of 84 responses")


def test_body_text_is_preserved_exactly():
    sections = split_briefing_sections(_REAL_BRIEFING)
    _, body = sections[2]  # SENTIMENT
    assert body == "Out of Firman's 12 mentions, 4 were negative or unfavorable."


def test_block_with_no_newline_gets_empty_header_not_dropped():
    """A malformed or model-deviation case shouldn't lose real content."""
    sections = split_briefing_sections("Just one plain sentence with no header at all.")
    assert sections == [("", "Just one plain sentence with no header at all.")]


def test_empty_or_none_text_returns_no_sections():
    assert split_briefing_sections("") == []
    assert split_briefing_sections(None) == []


def test_mixed_headered_and_headerless_blocks():
    text = "VISIBILITY SNAPSHOT\nReal section.\n\nJust a stray sentence.\n\nSENTIMENT\nAnother real one."
    sections = split_briefing_sections(text)
    assert sections == [
        ("VISIBILITY SNAPSHOT", "Real section."),
        ("", "Just a stray sentence."),
        ("SENTIMENT", "Another real one."),
    ]

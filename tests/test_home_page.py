"""
Tests for desktop/pages/home_page.py's _summarize_prompt_set() — Home's
Recent Activity feed was printing a Visibility run's raw prompt_set field
verbatim, which is a comma-joined string of every selected family name
(20+ families is the normal case for a real collection run), flooding the
feed with hundreds of characters of unreadable text per line.
"""
from desktop.pages.home_page import _summarize_prompt_set


def test_single_family_name_shown_as_is():
    assert _summarize_prompt_set("Best Generator Brand") == "Best Generator Brand"


def test_multiple_families_summarized_to_a_count():
    joined = ", ".join(f"Family {i}" for i in range(22))
    assert _summarize_prompt_set(joined) == "22 prompt sets"


def test_two_families_summarized_to_a_count():
    assert _summarize_prompt_set("Family A, Family B") == "2 prompt sets"


def test_empty_prompt_set_shows_a_placeholder():
    assert _summarize_prompt_set("") == "—"
    assert _summarize_prompt_set(None) == "—"

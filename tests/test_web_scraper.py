"""
Tests for backend/intelligence/web_scraper.py's AI-crawler robots.txt check
(#58) and its wiring into scrape_domain() (#57/#58).
"""
from unittest.mock import patch, MagicMock

from backend.intelligence.web_scraper import (
    _AI_CRAWLERS,
    _parse_robots_txt,
    _is_blocked,
    check_ai_crawler_access,
    scrape_domain,
)


def _fake_response(status_code=200, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.url = "https://example.com/"
    return resp


# ── _parse_robots_txt / _is_blocked ─────────────────────────────────────────

def test_parse_robots_txt_groups_consecutive_user_agents():
    text = """
    User-agent: GPTBot
    User-agent: ClaudeBot
    Disallow: /

    User-agent: *
    Disallow: /admin/
    """
    groups = _parse_robots_txt(text)
    assert len(groups) == 2
    agents0, rules0 = groups[0]
    assert agents0 == ["GPTBot", "ClaudeBot"]
    assert rules0 == [("disallow", "/")]
    agents1, rules1 = groups[1]
    assert agents1 == ["*"]
    assert rules1 == [("disallow", "/admin/")]


def test_parse_robots_txt_ignores_comments_and_unknown_directives():
    text = """
    # this is a comment
    User-agent: GPTBot
    Disallow: /   # inline comment
    Sitemap: https://example.com/sitemap.xml
    Crawl-delay: 10
    """
    groups = _parse_robots_txt(text)
    assert len(groups) == 1
    agents, rules = groups[0]
    assert agents == ["GPTBot"]
    assert rules == [("disallow", "/")]


def test_is_blocked_bare_disallow_root():
    assert _is_blocked([("disallow", "/")]) is True


def test_is_blocked_allow_root_overrides_disallow_root():
    assert _is_blocked([("disallow", "/"), ("allow", "/")]) is False


def test_is_blocked_partial_path_disallow_is_not_a_full_block():
    assert _is_blocked([("disallow", "/admin/")]) is False


def test_is_blocked_no_rules():
    assert _is_blocked([]) is False


# ── check_ai_crawler_access ──────────────────────────────────────────────────

def test_explicit_block_of_named_crawler():
    robots = "User-agent: GPTBot\nDisallow: /\n"
    with patch("backend.intelligence.web_scraper.requests.get",
               return_value=_fake_response(200, robots)):
        result = check_ai_crawler_access("example.com")

    assert result["has_robots_txt"] is True
    assert result["crawlers"]["GPTBot"] == {"blocked": True, "matched": "explicit"}
    assert "GPTBot" in result["blocked_crawler_names"]
    # Crawlers not mentioned at all, with no wildcard block, are unaffected.
    assert result["crawlers"]["ClaudeBot"] == {"blocked": False, "matched": "none"}


def test_wildcard_block_applies_to_unlisted_crawlers():
    robots = "User-agent: *\nDisallow: /\n"
    with patch("backend.intelligence.web_scraper.requests.get",
               return_value=_fake_response(200, robots)):
        result = check_ai_crawler_access("example.com")

    assert result["crawlers"]["GPTBot"] == {"blocked": True, "matched": "wildcard"}
    assert set(result["blocked_crawler_names"]) == set(_AI_CRAWLERS)


def test_named_crawler_own_group_overrides_wildcard_block():
    robots = (
        "User-agent: *\n"
        "Disallow: /\n\n"
        "User-agent: GPTBot\n"
        "Allow: /\n"
    )
    with patch("backend.intelligence.web_scraper.requests.get",
               return_value=_fake_response(200, robots)):
        result = check_ai_crawler_access("example.com")

    assert result["crawlers"]["GPTBot"] == {"blocked": False, "matched": "explicit"}
    assert result["crawlers"]["ClaudeBot"] == {"blocked": True, "matched": "wildcard"}
    assert "GPTBot" not in result["blocked_crawler_names"]
    assert "ClaudeBot" in result["blocked_crawler_names"]


def test_no_robots_txt_means_nothing_blocked():
    with patch("backend.intelligence.web_scraper.requests.get",
               return_value=_fake_response(404, "")):
        result = check_ai_crawler_access("example.com")

    assert result["has_robots_txt"] is False
    assert result["blocked_crawler_names"] == []


def test_network_error_is_reported_not_raised():
    with patch("backend.intelligence.web_scraper.requests.get",
               side_effect=Exception("connection refused")):
        result = check_ai_crawler_access("example.com")

    assert result["has_robots_txt"] is False
    assert "connection refused" in result["error"]


# ── scrape_domain() wiring ───────────────────────────────────────────────────

def test_scrape_domain_includes_crawler_result_even_when_homepage_fetch_fails():
    """
    The robots.txt check must not depend on the homepage fetch succeeding —
    a site can have a broken homepage but a perfectly reachable robots.txt,
    or vice versa.
    """
    robots = "User-agent: GPTBot\nDisallow: /\n"

    def fake_get(url, **kwargs):
        if url.endswith("/robots.txt"):
            return _fake_response(200, robots)
        return _fake_response(500, "")  # homepage fetch fails

    with patch("backend.intelligence.web_scraper.requests.get", side_effect=fake_get):
        result = scrape_domain("example.com")

    assert result["error"] == "HTTP 500"
    assert result["has_robots_txt"] is True
    assert result["blocks_ai_crawlers"] is True
    assert result["blocked_crawler_names"] == ["GPTBot"]


def test_scrape_domain_no_crawlers_blocked_when_robots_txt_absent():
    def fake_get(url, **kwargs):
        if url.endswith("/robots.txt"):
            return _fake_response(404, "")
        return _fake_response(200, "<html><head><title>Example</title></head></html>")

    with patch("backend.intelligence.web_scraper.requests.get", side_effect=fake_get), \
         patch("backend.intelligence.web_scraper.requests.head",
               return_value=_fake_response(200, "")):
        result = scrape_domain("example.com")

    assert result["has_robots_txt"] is False
    assert result["blocks_ai_crawlers"] is False
    assert result["blocked_crawler_names"] == []

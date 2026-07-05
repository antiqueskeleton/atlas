"""
Tests for IntelligenceService._build_web_block()'s handling of the own-site
flag and AI-crawler blocking (#57/#58) — confirms the briefing surfaces a
visible warning when the user's own site blocks a known AI crawler, and
stays silent for ordinary competitor rows or a clean own-site scrape.
"""
from unittest.mock import patch

from backend.intelligence.intelligence_service import IntelligenceService


class _FakePM:
    active_provider_name = "fake"


def _service():
    return IntelligenceService(_FakePM(), target_brand="TestOwnSiteXYZ")


def _row(brand="TestOwnSiteXYZ", domain="example.com", is_own_site=1,
         blocks_ai_crawlers=0, blocked_crawler_names="", scraped="2026-07-05T00:00:00"):
    return (
        brand, domain, "Title", "Meta desc", "[]", "keyword1, keyword2",
        0, 0,  # domain_authority, monthly_visits (unused, legacy)
        True, True, True,  # has_schema, has_sitemap, is_https
        scraped, is_own_site, blocks_ai_crawlers, blocked_crawler_names,
    )


def test_own_site_blocking_crawlers_surfaces_a_warning_line():
    row = _row(blocks_ai_crawlers=1, blocked_crawler_names="GPTBot, ClaudeBot")
    with patch("backend.knowledge.knowledge_repository.KnowledgeRepository") as MockRepo:
        MockRepo.return_value.list_web_intelligence_for_briefing.return_value = [row]
        block = _service()._build_web_block()

    assert "YOUR SITE" in block
    assert "BLOCKS these AI crawlers: GPTBot, ClaudeBot" in block


def test_own_site_not_blocking_crawlers_has_no_warning():
    row = _row(blocks_ai_crawlers=0, blocked_crawler_names="")
    with patch("backend.knowledge.knowledge_repository.KnowledgeRepository") as MockRepo:
        MockRepo.return_value.list_web_intelligence_for_briefing.return_value = [row]
        block = _service()._build_web_block()

    assert "YOUR SITE" in block
    assert "BLOCKS" not in block


def test_competitor_row_blocking_crawlers_is_not_flagged_as_a_warning():
    """
    Only the OWN site's blocking matters for this warning — a competitor
    blocking AI crawlers on their own site isn't Atlas's/the user's problem
    to fix, so it shouldn't render as an actionable warning line.
    """
    row = _row(brand="CompetitorBrand", is_own_site=0,
               blocks_ai_crawlers=1, blocked_crawler_names="GPTBot")
    with patch("backend.knowledge.knowledge_repository.KnowledgeRepository") as MockRepo:
        MockRepo.return_value.list_web_intelligence_for_briefing.return_value = [row]
        block = _service()._build_web_block()

    assert "YOUR SITE" not in block
    assert "BLOCKS" not in block

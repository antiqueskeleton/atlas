"""
Tests for #96 — provider-reported citation capture and aggregation.
Perplexity returns the source URLs it grounded each answer on; Atlas
previously discarded them. They now flow provider → runner → repository →
domain aggregation → briefing web block.
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from backend.ai.perplexity_provider import PerplexityProvider, _extract_citations
from backend.models.visibility_response import VisibilityResponse
from backend.visibility.visibility_repository import VisibilityRepository


def _fake_perplexity_response(text, citations=None, search_results=None):
    message = SimpleNamespace(content=text)
    choice = SimpleNamespace(message=message)
    resp = SimpleNamespace(choices=[choice], model_extra={})
    if citations is not None:
        resp.citations = citations
    if search_results is not None:
        resp.search_results = search_results
    return resp


# ── Extraction ────────────────────────────────────────────────────────────────

def test_extract_citations_from_top_level_list():
    resp = _fake_perplexity_response("answer", citations=[
        "https://www.wirecutter.com/best-generators/",
        "https://old.reddit.com/r/Generators/abc",
    ])
    assert _extract_citations(resp) == [
        "https://www.wirecutter.com/best-generators/",
        "https://old.reddit.com/r/Generators/abc",
    ]


def test_extract_citations_merges_search_results_and_dedupes():
    resp = _fake_perplexity_response(
        "answer",
        citations=["https://a.com/x"],
        search_results=[{"url": "https://a.com/x"}, {"url": "https://b.com/y"}],
    )
    assert _extract_citations(resp) == ["https://a.com/x", "https://b.com/y"]


def test_extract_citations_never_raises_on_weird_shapes():
    resp = _fake_perplexity_response("answer", citations=[None, 42, "not-a-url"])
    assert _extract_citations(resp) == []


def test_provider_attaches_citations_to_successful_response():
    provider = PerplexityProvider()
    provider.set_api_key("fake-key")
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_perplexity_response(
        "Firman is a solid choice.", citations=["https://bobvila.com/generators"]
    )
    with patch("openai.OpenAI", return_value=fake_client):
        result = provider.ask("best generator")
    assert result.is_error is False
    assert result.citations == ["https://bobvila.com/generators"]


# ── Storage + aggregation ─────────────────────────────────────────────────────

def _save(repo, url_lists):
    now = datetime.now()
    repo.save_responses([
        VisibilityResponse("r1", "Perplexity", "sonar", f"q{i}", "text", now,
                           "fam", citations=urls)
        for i, urls in enumerate(url_lists)
    ])


def test_citation_domain_counts_aggregates_and_strips_www(tmp_path):
    repo = VisibilityRepository(db_path=tmp_path / "v.db")
    _save(repo, [
        ["https://www.wirecutter.com/a", "https://reddit.com/r/x"],
        ["https://wirecutter.com/b"],
        None,  # provider without citations → NULL column, ignored
    ])
    result = repo.citation_domain_counts()
    assert result["responses_with_citations"] == 2
    domains = {d: (c, r) for d, c, r in result["domains"]}
    assert domains["wirecutter.com"] == (2, 2)  # www stripped, both responses
    assert domains["reddit.com"] == (1, 1)


def test_citation_domain_counts_empty_db(tmp_path):
    repo = VisibilityRepository(db_path=tmp_path / "v.db")
    result = repo.citation_domain_counts()
    assert result["domains"] == []
    assert result["responses_with_citations"] == 0

"""
Tests for _run_live() (#44) — the 14-prompt live-collection fallback path
used for brand-new target brands or when DB history is insufficient. This
path shares the portfolio pass, negative-mention wiring, and error handling
added this session with the more commonly-exercised DB-backed path, but had
never been run or tested since those changes landed.

Uses a fake provider and a throwaway temp DB (via tmp_path) so this never
touches real API quota or the real atlas.db.
"""
from types import SimpleNamespace

from backend.intelligence.intelligence_service import IntelligenceService
from backend.intelligence.intelligence_repository import IntelligenceRepository


class _FakeProvider:
    provider_name = "FakeProvider"
    model = "fake-model"

    def __init__(self):
        self.calls: list[str] = []

    def ask(self, prompt):
        self.calls.append(prompt)
        n = len(self.calls)
        if "OPPORTUNITY [N]" in prompt or "Identify the top 5" in prompt:
            return SimpleNamespace(executive_summary=(
                "OPPORTUNITY [1]: Test opportunity from live path\n"
                "EVIDENCE: 1 of 14 responses\nACTION: Test action\nTACTICS: Test tactic"
            ))
        if "VISIBILITY SNAPSHOT" in prompt and "Produce a structured" in prompt:
            return SimpleNamespace(executive_summary="VISIBILITY SNAPSHOT\nTest briefing from live path.")
        if prompt.strip().startswith("You are analyzing AI-generated research responses"):
            return SimpleNamespace(executive_summary=(
                "IN PORTFOLIO: Portable Generators\n"
                "NOT IN PORTFOLIO: Home Standby\n"
                "UNCERTAIN: none"
            ))
        return SimpleNamespace(executive_summary=f"Fake analyst answer #{n} mentioning Firman and Honda.")


class _FakePM:
    active_provider_name = "fake"

    def __init__(self, provider):
        self._provider = provider

    def set_active_provider(self, name):
        pass

    def get_active_provider(self):
        return self._provider


def test_run_live_completes_and_makes_exactly_17_calls(tmp_path):
    """14 analyst prompts (5 product + 4 persona + 5 journey) + 3 synthesis
    passes (portfolio, opportunity, briefing) = 17 total provider calls."""
    provider = _FakeProvider()
    svc = IntelligenceService(_FakePM(provider), target_brand="Firman")
    svc.repository = IntelligenceRepository(db_path=str(tmp_path / "test_intelligence.db"))

    result = svc._run_live(provider_name=None)

    assert result["source"] == "live"
    assert result["responses_used"] == 14
    assert len(provider.calls) == 17


def test_run_live_threads_portfolio_block_into_opportunity_and_briefing():
    provider = _FakeProvider()
    svc = IntelligenceService(_FakePM(provider), target_brand="Firman")
    import tempfile, os
    svc.repository = IntelligenceRepository(
        db_path=os.path.join(tempfile.mkdtemp(), "test.db")
    )

    svc._run_live(provider_name=None)

    opp_prompt = next(c for c in provider.calls if "Identify the top 5" in c)
    assert "NOT IN PORTFOLIO" in opp_prompt

    brief_prompt = next(
        c for c in provider.calls if "VISIBILITY SNAPSHOT" in c and "Produce a structured" in c
    )
    assert "NOT IN PORTFOLIO" in brief_prompt


def test_run_live_persists_parsed_opportunity_to_a_fresh_db(tmp_path):
    """
    Regression test: IntelligenceRepository previously only ALTERed the
    opportunities table, assuming KnowledgeRepository had already created it
    elsewhere. On a database where NOTHING else has touched opportunities
    yet, save_opportunities() would crash with "no such table: opportunities".
    Fixed by giving IntelligenceRepository its own defensive
    CREATE TABLE IF NOT EXISTS, matching every other table in the codebase.
    """
    provider = _FakeProvider()
    svc = IntelligenceService(_FakePM(provider), target_brand="Firman")
    svc.repository = IntelligenceRepository(db_path=str(tmp_path / "fresh.db"))

    result = svc._run_live(provider_name=None)

    saved = svc.repository.get_opportunities_for_run(result["run_id"])
    assert len(saved) == 1
    assert "Test opportunity from live path" in saved[0][1]  # title column

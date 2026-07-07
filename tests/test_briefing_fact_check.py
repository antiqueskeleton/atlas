"""
Tests for #95 — deterministic verification of the briefing's "X of Y"
claims against the exact source blocks fed to the model.
"""
import json

from backend.intelligence.briefing_fact_check import verify_briefing_numbers


def test_all_claims_verified_when_pairs_exist_in_sources():
    briefing = ("Firman appeared in 10 of 71 responses, ranking #12 of 29 "
                "tracked brands.")
    sources = ["Firman: 10 of 71 responses (14%), rank #12 of 29"]
    result = verify_briefing_numbers(briefing, sources)
    assert result["total_claims"] == 2
    assert result["verified"] == 2
    assert result["unverified"] == []


def test_invented_pair_is_flagged_with_context():
    briefing = "Champion led with 46 of 71 responses. Honda had 99 of 500."
    sources = ["Champion: 46 of 71 responses"]
    result = verify_briefing_numbers(briefing, sources)
    assert result["total_claims"] == 2
    assert result["verified"] == 1
    assert len(result["unverified"]) == 1
    assert result["unverified"][0]["claim"] == "99 of 500"
    assert "Honda" in result["unverified"][0]["context"]


def test_out_of_phrasing_and_thousands_separators():
    briefing = "It was cited in 1,200 out of 8,252 responses."
    sources = ["total: 1200 of 8252"]
    result = verify_briefing_numbers(briefing, sources)
    assert result["verified"] == 1  # comma formatting must not break matching


def test_no_claims_yields_empty_result():
    result = verify_briefing_numbers("No numbers here at all.", ["10 of 20"])
    assert result == {"total_claims": 0, "verified": 0, "unverified": []}


def test_verification_persisted_with_briefing(tmp_path):
    """End to end through _run_live: the verification JSON lands in the
    briefings table at index 6 of get_briefing_for_run."""
    from tests.test_run_live import _FakePM, _FakeProvider
    from types import SimpleNamespace
    from backend.intelligence.intelligence_service import IntelligenceService
    from backend.intelligence.intelligence_repository import IntelligenceRepository
    from backend.visibility.visibility_repository import VisibilityRepository

    class _CitingProvider(_FakeProvider):
        def ask(self, prompt):
            if "VISIBILITY SNAPSHOT" in prompt and "Produce a structured" in prompt:
                self.calls.append(prompt)
                return SimpleNamespace(
                    executive_summary=("VISIBILITY SNAPSHOT\n"
                                       "Firman appeared in 999 of 12345 responses."),
                    is_error=False)
            return super().ask(prompt)

    provider = _CitingProvider()
    svc = IntelligenceService(_FakePM(provider), target_brand="Firman")
    svc.repository = IntelligenceRepository(db_path=str(tmp_path / "test.db"))
    svc.visibility_repository = VisibilityRepository(db_path=tmp_path / "vis.db")

    result = svc._run_live(provider_name=None)

    briefing = svc.repository.get_briefing_for_run(result["run_id"])
    verification = json.loads(briefing[6])
    assert verification["total_claims"] == 1
    # "999 of 12345" was invented — it appears nowhere in the source blocks
    assert verification["verified"] == 0
    assert verification["unverified"][0]["claim"] == "999 of 12,345"

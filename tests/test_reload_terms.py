"""
Tests for VisibilityAnalytics.reload_terms() (#35) — brand/feature/channel
detection terms were previously loaded once at construction and never
refreshed, so a brand added via the Knowledge page mid-session silently
never showed up in Visibility/Trends analytics until the app restarted.

Mocks KnowledgeRepository.get_brand_detection_terms() to simulate a brand
being added between two calls, without touching the real Knowledge database.
"""
from datetime import datetime
from unittest.mock import patch

from backend.models.visibility_response import VisibilityResponse
from backend.models.visibility_run import VisibilityRun
from backend.visibility.visibility_analytics import VisibilityAnalytics
from backend.visibility.visibility_repository import VisibilityRepository
from backend.visibility.visibility_service import VisibilityService


_KR_PATCH_TARGET = "backend.knowledge.knowledge_repository.KnowledgeRepository.get_brand_detection_terms"


def test_reload_terms_picks_up_a_newly_added_brand():
    with patch(_KR_PATCH_TARGET, return_value={"Firman": ["firman"], "Honda": ["honda"]}):
        a = VisibilityAnalytics(target_brand="Firman")
        assert set(a.brands) == {"Firman", "Honda"}

    # Simulate a brand added via the Knowledge page mid-session
    with patch(
        _KR_PATCH_TARGET,
        return_value={"Firman": ["firman"], "Honda": ["honda"], "Generac": ["generac"]},
    ):
        changed = a.reload_terms()
        assert changed is True
        assert set(a.brands) == {"Firman", "Honda", "Generac"}
        # _flat_brand_terms must also be rebuilt, not just self.brands
        assert ("generac", "Generac") in a._flat_brand_terms


def test_reload_terms_returns_false_when_nothing_changed():
    with patch(_KR_PATCH_TARGET, return_value={"Firman": ["firman"], "Honda": ["honda"]}):
        a = VisibilityAnalytics(target_brand="Firman")
        changed = a.reload_terms()  # identical data, nothing changed
        assert changed is False


def test_reload_terms_detects_a_removed_brand_too():
    with patch(
        _KR_PATCH_TARGET,
        return_value={"Firman": ["firman"], "Honda": ["honda"], "Generac": ["generac"]},
    ):
        a = VisibilityAnalytics(target_brand="Firman")

    with patch(_KR_PATCH_TARGET, return_value={"Firman": ["firman"], "Honda": ["honda"]}):
        changed = a.reload_terms()
        assert changed is True
        assert "Generac" not in a.brands


def test_newly_reloaded_brand_is_actually_detected_in_responses():
    """
    End-to-end within VisibilityAnalytics: a brand added via reload_terms()
    must be usable by summarize_responses() immediately afterward, not just
    present in self.brands.
    """
    with patch(_KR_PATCH_TARGET, return_value={"Firman": ["firman"]}):
        a = VisibilityAnalytics(target_brand="Firman")

    with patch(_KR_PATCH_TARGET, return_value={"Firman": ["firman"], "Generac": ["generac"]}):
        a.reload_terms()

    responses = [(1, "r1", "openai", "model", "q1", "Generac is a strong competitor.", "2026-07-01", "fam1")]
    result = a.summarize_responses(responses)
    assert result["brand_counts"].get("Generac") == 1


# ── VisibilityService.analytics_summary() cache invalidation ─────────────────

def test_analytics_summary_cache_invalidates_when_terms_change_even_if_response_count_does_not(tmp_path):
    """
    The real #35 bug scenario: a brand is added via Knowledge with ZERO new
    Visibility responses collected. The response-count-keyed cache alone
    would never notice — analytics_summary() must invalidate it separately
    whenever reload_terms() reports a real term change.
    """
    class _FakePM:
        active_provider_name = "fake"

    with patch(_KR_PATCH_TARGET, return_value={"Firman": ["firman"]}):
        svc = VisibilityService(_FakePM(), target_brand="Firman")

    svc.repository = VisibilityRepository(db_path=str(tmp_path / "test.db"))
    svc.repository.save_run(VisibilityRun(
        run_id="r1", provider="openai", model="m", prompt_set="fam1",
        started_at=datetime(2026, 7, 1), completed_at=datetime(2026, 7, 1, 0, 1),
        status="completed", response_count=1, duration_seconds=1.0,
    ))
    svc.repository.save_responses([VisibilityResponse(
        run_id="r1", provider="openai", model="m", prompt="q1",
        response="Firman is a solid choice.", collected_at=datetime(2026, 7, 1, 0, 0, 30),
        family_name="fam1",
    )])

    with patch(_KR_PATCH_TARGET, return_value={"Firman": ["firman"]}):
        first = svc.analytics_summary()
        assert first["total_tracked_brands"] == 1

    # Brand added via Knowledge — deliberately NO new responses collected,
    # so response count is identical to the first call. If cache invalidation
    # relied on response count alone, this would never be picked up. Generac
    # isn't actually mentioned in the one stored response, so brand_counts
    # itself wouldn't change either way — total_tracked_brands (from #48) is
    # the field that specifically proves the term SET was reloaded, since it
    # counts all tracked brands regardless of whether they have a mention.
    with patch(
        _KR_PATCH_TARGET,
        return_value={"Firman": ["firman"], "Generac": ["generac"]},
    ):
        second = svc.analytics_summary()
        assert second["total_tracked_brands"] == 2

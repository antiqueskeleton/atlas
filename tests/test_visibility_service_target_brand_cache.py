"""
Tests for VisibilityService.analytics_summary()'s target_brand cache
invalidation (#80) — the Visibility page's target_visibility_score tile
went stale (showed 0.0% against a real, non-zero dataset) because the
analytics cache was only keyed on response COUNT, not on target_brand.
Changing the target brand in Settings after the Visibility page was
already constructed (all pages are built once at app startup) had no
effect on the score until the response count next changed, since nothing
told the cache the target brand itself had changed.
"""
from backend.ai.provider_manager import ProviderManager
from backend.visibility.visibility_repository import VisibilityRepository
from backend.visibility.visibility_service import VisibilityService


def _service_with_data(tmp_path):
    service = VisibilityService(ProviderManager(), target_brand="Firman")
    service.repository = VisibilityRepository(db_path=tmp_path / "test.db")
    # 1 of 3 responses mention Firman (33.3%), 2 of 3 mention Honda (66.7%) —
    # deliberately different rates so a stale cache is obviously wrong,
    # not coincidentally correct.
    texts = [
        "Firman is a solid choice.",
        "Honda is a solid choice.",
        "Honda is also quite reliable.",
    ]
    with service.repository.connect() as conn:
        for i, text in enumerate(texts):
            conn.execute(
                "INSERT INTO visibility_responses (run_id, provider, model, prompt, response, collected_at) "
                "VALUES (?,?,?,?,?,?)",
                ("run-1", "openai", "gpt-4.1-mini", "best generator", text,
                 f"2026-07-05T10:00:0{i}"),
            )
    return service


def test_analytics_summary_reflects_current_target_brand(tmp_path):
    service = _service_with_data(tmp_path)
    result = service.analytics_summary()
    assert result["target_visibility_score"] == 33.3  # 1 of 3 responses mention Firman


def test_changing_target_brand_invalidates_the_cache_with_same_response_count(tmp_path):
    """
    The core #80 regression: switch target_brand WITHOUT adding any new
    responses (the exact real-world scenario — user changes Target Brand in
    Settings, no new collection has run yet) and confirm the score updates
    to reflect the NEW brand, not a stale cached value from the old one.
    """
    service = _service_with_data(tmp_path)
    first = service.analytics_summary()
    assert first["target_visibility_score"] == 33.3  # Firman: 1 of 3

    # Simulate what visibility_page.py's refresh() now does on every call.
    service.target_brand = "Honda"
    service.analytics.target_brand = "Honda"

    second = service.analytics_summary()
    assert second["target_visibility_score"] == 66.7  # Honda: 2 of 3 — proves it's NOT the stale Firman value


def test_cache_is_reused_when_target_brand_and_count_are_unchanged(tmp_path):
    service = _service_with_data(tmp_path)
    first = service.analytics_summary()
    second = service.analytics_summary()
    assert first is second  # same cached object, not recomputed

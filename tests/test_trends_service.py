"""
Tests for backend/visibility/trends_service.py's target-brand resolution
(#82). Built via __new__() with hand-set attributes so these don't touch
the real database.
"""
from backend.visibility.trends_service import TrendsService


def make_service(target_brand):
    s = TrendsService.__new__(TrendsService)
    s.target_brand = target_brand
    s.analytics = type("FakeAnalytics", (), {"brands": ["Firman", "Honda", "Generac"]})()
    return s


def _summary(brand_rates):
    return {"brand_rates": brand_rates, "first_mention_share": brand_rates}


def test_brand_time_series_resolves_wrong_cased_target_to_canonical_entry():
    """
    Before the fix, a target_brand of "FIRMAN" wouldn't match the "Firman"
    key already present in `selected` (from summaries' brand_rates, which
    are always keyed by canonical casing) — it would append a second,
    all-zero, wrong-cased "FIRMAN" entry instead of just keeping the real
    "Firman" data already selected.
    """
    summaries = [_summary({"Firman": 40.0, "Honda": 60.0})]
    s = make_service("FIRMAN")
    series = s.brand_time_series(summaries, top_n=1)

    assert "FIRMAN" not in series          # no bogus wrong-cased ghost entry
    assert series["Firman"] == [40.0]      # real data preserved


def test_brand_snapshot_resolves_wrong_cased_target_to_canonical_entry():
    summaries = [_summary({"Firman": 40.0, "Honda": 60.0})]
    s = make_service("firman")
    snapshot = s.brand_snapshot(summaries, top_n=1)

    assert "firman" not in snapshot
    assert snapshot["Firman"] == 40.0


def test_position_time_series_resolves_wrong_cased_target_to_canonical_entry():
    summaries = [_summary({"Firman": 10.0, "Honda": 90.0})]
    s = make_service("FiRmAn")
    series = s.position_time_series(summaries, top_n=1)

    assert "FiRmAn" not in series
    assert series["Firman"] == [10.0]


# ── Model-change event markers (#90) ─────────────────────────────────────────

class _FakeVisRepo:
    def __init__(self, runs):
        self._runs = runs

    def list_runs(self):
        return self._runs


class _FakeKnowRepo:
    def __init__(self, existing=None):
        self.logged = []
        self._existing = existing or []

    def list_events(self):
        return self._existing

    def log_event(self, event_type, description, occurred_at=None):
        self.logged.append((event_type, description, occurred_at))


def _run(provider, model, started_at):
    return (f"id-{provider}-{started_at}", provider, model, "fam", started_at,
            None, "completed", 10, 5.0)


def test_sync_logs_model_transition_dated_at_the_change():
    from backend.visibility.trends_service import sync_model_change_events
    vis = _FakeVisRepo([
        _run("openai", "gpt-4o", "2026-06-01T10:00:00"),
        _run("openai", "gpt-4o", "2026-06-08T10:00:00"),
        _run("openai", "gpt-4.1", "2026-06-15T10:00:00"),  # transition here
        _run("anthropic", "claude-x", "2026-06-15T11:00:00"),  # no transition
    ])
    know = _FakeKnowRepo()
    logged = sync_model_change_events(vis, know)
    assert logged == 1
    event_type, description, occurred_at = know.logged[0]
    assert event_type == "model_change"
    assert "gpt-4o" in description and "gpt-4.1" in description
    assert occurred_at == "2026-06-15T10:00:00"  # dated at the transition


def test_sync_is_idempotent_against_already_logged_events():
    from backend.visibility.trends_service import sync_model_change_events
    vis = _FakeVisRepo([
        _run("openai", "gpt-4o", "2026-06-01T10:00:00"),
        _run("openai", "gpt-4.1", "2026-06-15T10:00:00"),
    ])
    existing = [("model_change", "openai model changed: gpt-4o → gpt-4.1",
                 "2026-06-15T10:00:00")]
    know = _FakeKnowRepo(existing=existing)
    assert sync_model_change_events(vis, know) == 0
    assert know.logged == []


def test_sync_handles_out_of_order_rows_and_no_runs():
    from backend.visibility.trends_service import sync_model_change_events
    # Rows arrive newest-first (as list_runs returns them) — the walk must
    # still see the transition in chronological order, exactly once.
    vis = _FakeVisRepo([
        _run("openai", "gpt-4.1", "2026-06-15T10:00:00"),
        _run("openai", "gpt-4o", "2026-06-01T10:00:00"),
    ])
    know = _FakeKnowRepo()
    assert sync_model_change_events(vis, know) == 1
    assert sync_model_change_events(_FakeVisRepo([]), _FakeKnowRepo()) == 0

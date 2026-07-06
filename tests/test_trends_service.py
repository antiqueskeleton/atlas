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

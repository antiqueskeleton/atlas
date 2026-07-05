"""
Tests for TrendsService.detect_visibility_drops() (#59) — flags a provider
whose latest run scored meaningfully below its own trailing baseline.
Compared per-provider rather than pooled, since providers have very
different natural baseline visibility levels (mixing them would make a
provider-mix shift look like a real drop).
"""
from backend.visibility.trends_service import TrendsService


def _summary(provider, score, date):
    return {
        "run_id": 1, "datetime": f"{date}T00:00:00", "date": date, "label": date,
        "provider": provider, "prompt_set": "Test", "response_count": 10,
        "target_score": score, "brand_rates": {}, "feature_rates": {},
        "brand_position_shares": {}, "first_mention_share": {},
    }


def _service():
    return TrendsService.__new__(TrendsService)


def test_no_drop_when_score_holds_steady():
    svc = _service()
    summaries = [_summary("openai", 60, f"2026-07-0{i}") for i in range(1, 6)]
    assert svc.detect_visibility_drops(summaries) == []


def test_flags_a_real_drop_below_threshold():
    svc = _service()
    summaries = [_summary("openai", 65, f"2026-07-0{i}") for i in range(1, 5)]
    summaries.append(_summary("openai", 40, "2026-07-05"))  # -25 pts vs baseline 65

    drops = svc.detect_visibility_drops(summaries)
    assert len(drops) == 1
    d = drops[0]
    assert d["provider"] == "openai"
    assert d["baseline_score"] == 65.0
    assert d["latest_score"] == 40
    assert d["drop"] == 25.0
    assert d["latest_date"] == "2026-07-05"


def test_small_fluctuation_under_threshold_is_not_flagged():
    svc = _service()
    summaries = [_summary("openai", 60, f"2026-07-0{i}") for i in range(1, 5)]
    summaries.append(_summary("openai", 50, "2026-07-05"))  # -10 pts, under 15pt threshold
    assert svc.detect_visibility_drops(summaries) == []


def test_insufficient_history_is_not_flagged_even_with_a_big_drop():
    svc = _service()
    # Only 2 prior runs — fewer than _MIN_PRIOR_RUNS (3) — must not flag,
    # regardless of how big the apparent drop looks with so little history.
    summaries = [_summary("openai", 90, "2026-07-01"), _summary("openai", 90, "2026-07-02")]
    summaries.append(_summary("openai", 10, "2026-07-03"))
    assert svc.detect_visibility_drops(summaries) == []


def test_providers_are_evaluated_independently_not_pooled():
    """
    A newest run happening to be from a naturally-lower-scoring provider
    must not look like a drop for a different, unaffected provider.
    """
    svc = _service()
    summaries = [_summary("openai", 70, f"2026-07-0{i}") for i in range(1, 5)]
    summaries += [_summary("perplexity", 20, f"2026-07-0{i}") for i in range(1, 5)]
    summaries.append(_summary("perplexity", 15, "2026-07-05"))  # tiny real drop, under threshold

    assert svc.detect_visibility_drops(summaries) == []


def test_baseline_uses_only_the_trailing_window_not_full_history():
    """
    An old high score from long ago shouldn't inflate today's baseline once
    more recent runs exist — baseline is the trailing _BASELINE_WINDOW (5)
    runs immediately before the latest one, not all history.
    """
    svc = _service()
    summaries = [_summary("openai", 95, "2026-06-01")]  # old, outside the window
    summaries += [_summary("openai", 40, f"2026-07-0{i}") for i in range(1, 6)]  # 5 recent runs
    summaries.append(_summary("openai", 20, "2026-07-06"))  # -20 vs recent baseline of 40

    drops = svc.detect_visibility_drops(summaries)
    assert len(drops) == 1
    assert drops[0]["baseline_score"] == 40.0


def test_multiple_flagged_providers_sorted_by_severity_descending():
    svc = _service()
    summaries = [_summary("openai", 65, f"2026-07-0{i}") for i in range(1, 5)]
    summaries.append(_summary("openai", 40, "2026-07-05"))       # -25
    summaries += [_summary("gemini", 60, f"2026-07-0{i}") for i in range(1, 5)]
    summaries.append(_summary("gemini", 44, "2026-07-05"))       # -16

    drops = svc.detect_visibility_drops(summaries)
    assert [d["provider"] for d in drops] == ["openai", "gemini"]


def test_baseline_of_zero_is_never_flagged():
    """A provider that was already at 0 can't meaningfully 'drop' further."""
    svc = _service()
    summaries = [_summary("openai", 0, f"2026-07-0{i}") for i in range(1, 5)]
    summaries.append(_summary("openai", 0, "2026-07-05"))
    assert svc.detect_visibility_drops(summaries) == []

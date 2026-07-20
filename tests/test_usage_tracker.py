"""
API usage metering (R9): cost estimation and the SDK-shape normalizer are
pure and tested directly; the repository rollup runs against a tmp-path
database. The opt-in guarantee (metering off unless the app enables it) is
tested explicitly because it is what keeps provider unit tests from writing
into the real %APPDATA% database.
"""
from datetime import datetime
from types import SimpleNamespace

from backend.usage import usage_tracker as ut
from backend.usage.usage_repository import UsageRepository


# ── Cost estimation ───────────────────────────────────────────────────────────

def test_estimate_cost_uses_longest_matching_rate_key():
    """gpt-4.1-mini must not be priced as gpt-4.1 — the specific variant is
    ~5x cheaper, so longest-key-first matching is load-bearing."""
    mini = ut.estimate_cost("gpt-4.1-mini", 1_000_000, 1_000_000)
    base = ut.estimate_cost("gpt-4.1", 1_000_000, 1_000_000)
    assert mini == 0.40 + 1.60
    assert base == 2.00 + 8.00
    assert mini < base


def test_estimate_cost_scales_with_tokens():
    assert ut.estimate_cost("gpt-4.1-mini", 500_000, 0) == 0.20
    assert ut.estimate_cost("gpt-4.1-mini", 0, 500_000) == 0.80


def test_estimate_cost_unknown_model_returns_none_not_a_guess():
    """An unknown model must yield None (renders as "—"), never a fabricated
    number — the no-fake-data rule applies to cost too."""
    assert ut.estimate_cost("some-brand-new-model-9000", 1000, 1000) is None
    assert ut.estimate_cost("", 1000, 1000) is None
    assert ut.estimate_cost(None, 1000, 1000) is None


# ── Usage extraction across real SDK response shapes ──────────────────────────

def test_extract_usage_openai_responses_api():
    resp = SimpleNamespace(usage=SimpleNamespace(input_tokens=120, output_tokens=45))
    assert ut.extract_usage(resp) == (120, 45)


def test_extract_usage_chat_completions_shape():
    """DeepSeek / Mistral / Grok / Perplexity all use prompt/completion_tokens."""
    resp = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=80, completion_tokens=20))
    assert ut.extract_usage(resp) == (80, 20)


def test_extract_usage_cohere_nests_counts_under_tokens():
    resp = SimpleNamespace(usage=SimpleNamespace(
        tokens=SimpleNamespace(input_tokens=33, output_tokens=7)))
    assert ut.extract_usage(resp) == (33, 7)


def test_extract_usage_gemini_usage_metadata():
    resp = SimpleNamespace(usage_metadata=SimpleNamespace(
        prompt_token_count=64, candidates_token_count=16))
    assert ut.extract_usage(resp) == (64, 16)


def test_extract_usage_degrades_to_zero_never_raises():
    assert ut.extract_usage(SimpleNamespace()) == (0, 0)
    assert ut.extract_usage(None) == (0, 0)
    assert ut.extract_usage(SimpleNamespace(usage=None)) == (0, 0)
    assert ut.extract_usage(SimpleNamespace(usage="not-an-object")) == (0, 0)


# ── Opt-in guarantee ──────────────────────────────────────────────────────────

def test_recording_is_off_by_default_so_tests_never_touch_the_real_db():
    """record_usage must be a silent no-op until the app enables it. This is
    what stops provider unit tests writing into the real database."""
    ut.disable_recording()
    assert ut.is_enabled() is False
    ut.record_usage("OpenAI", "gpt-4.1-mini",
                    SimpleNamespace(usage=SimpleNamespace(input_tokens=10, output_tokens=5)))
    assert ut.month_to_date() == []          # nothing recorded, nothing raised


def test_enable_recording_then_record_and_rollup(tmp_path):
    ut.enable_recording(UsageRepository(db_path=tmp_path / "u.db"))
    try:
        assert ut.is_enabled() is True
        ut.record_usage("OpenAI", "gpt-4.1-mini",
                        SimpleNamespace(usage=SimpleNamespace(
                            input_tokens=1_000_000, output_tokens=1_000_000)))
        rows = ut.month_to_date()
        assert len(rows) == 1
        assert rows[0]["provider"] == "OpenAI"
        assert rows[0]["calls"] == 1
        assert rows[0]["input_tokens"] == 1_000_000
        assert rows[0]["est_cost"] == 2.00        # 0.40 in + 1.60 out
    finally:
        ut.disable_recording()


# ── Repository rollup ─────────────────────────────────────────────────────────

def _repo(tmp_path):
    return UsageRepository(db_path=tmp_path / "u.db")


def test_month_to_date_excludes_prior_months(tmp_path):
    repo = _repo(tmp_path)
    now = datetime(2026, 7, 17, 12, 0, 0)
    repo.record("OpenAI", "gpt-4.1-mini", 100, 50, 0.10, ts="2026-06-30T23:59:59")
    repo.record("OpenAI", "gpt-4.1-mini", 200, 60, 0.20, ts="2026-07-01T00:00:01")
    rows = repo.month_to_date(now=now)
    assert len(rows) == 1
    assert rows[0]["calls"] == 1                  # the June row is excluded
    assert rows[0]["input_tokens"] == 200


def test_month_to_date_groups_by_provider_and_sorts_by_cost(tmp_path):
    repo = _repo(tmp_path)
    now = datetime(2026, 7, 17, 12, 0, 0)
    stamp = "2026-07-05T10:00:00"
    repo.record("OpenAI", "gpt-4.1-mini", 100, 100, 0.05, ts=stamp)
    repo.record("OpenAI", "gpt-4.1-mini", 100, 100, 0.05, ts=stamp)
    repo.record("Anthropic", "claude-sonnet-4-6", 200, 200, 1.00, ts=stamp)
    rows = repo.month_to_date(now=now)
    assert [r["provider"] for r in rows] == ["Anthropic", "OpenAI"]   # cost desc
    openai = next(r for r in rows if r["provider"] == "OpenAI")
    assert openai["calls"] == 2 and openai["est_cost"] == 0.10


def test_month_to_date_marks_partial_and_all_unknown_costs(tmp_path):
    repo = _repo(tmp_path)
    now = datetime(2026, 7, 17, 12, 0, 0)
    stamp = "2026-07-05T10:00:00"
    # Provider with a mix of known and unknown rates -> partial estimate
    repo.record("OpenAI", "gpt-4.1-mini", 10, 10, 0.02, ts=stamp)
    repo.record("OpenAI", "mystery-model", 10, 10, None, ts=stamp)
    # Provider where nothing had a known rate -> est_cost stays None
    repo.record("Grok-X", "unknown-model", 10, 10, None, ts=stamp)
    rows = {r["provider"]: r for r in repo.month_to_date(now=now)}
    assert rows["OpenAI"]["est_cost"] == 0.02
    assert rows["OpenAI"]["cost_partial"] is True
    assert rows["Grok-X"]["est_cost"] is None
    assert rows["Grok-X"]["cost_partial"] is False

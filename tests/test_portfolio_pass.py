"""
Tests for the portfolio inference pass in intelligence_service.py (#30).

Uses a fake provider that captures prompts instead of calling a real API —
these tests exist to catch prompt-template wiring bugs (missing .format()
placeholders, portfolio_block not reaching downstream prompts), not to
evaluate LLM output quality.
"""
from types import SimpleNamespace

from backend.intelligence.intelligence_service import IntelligenceService


class _FakeProvider:
    provider_name = "fake"
    model = "fake-model"

    def __init__(self, canned_responses):
        self.canned = canned_responses
        self.calls: list[str] = []

    def ask(self, prompt):
        self.calls.append(prompt)
        text = self.canned[len(self.calls) - 1]
        return SimpleNamespace(executive_summary=text, is_error=False)


class _FailingProvider:
    """Simulates an API failure (rate limit, timeout, bad key, etc)."""
    provider_name = "fake"
    model = "fake-model"

    def __init__(self, message="simulated rate limit error"):
        self.message = message
        self.calls: list[str] = []

    def ask(self, prompt):
        self.calls.append(prompt)
        raise RuntimeError(self.message)


class _ErroringProvider:
    """
    Simulates the more common real-world failure shape: providers don't raise,
    they catch their own exceptions and return is_error=True with the failure
    text as executive_summary (see backend/ai/*_provider.py). Distinct from
    _FailingProvider above, which exercises the raising path.
    """
    provider_name = "fake"
    model = "fake-model"

    def __init__(self, message="simulated rate limit error"):
        self.message = message
        self.calls: list[str] = []

    def ask(self, prompt):
        self.calls.append(prompt)
        return SimpleNamespace(executive_summary=self.message, is_error=True)


class _FakePM:
    active_provider_name = "fake"


def _service():
    return IntelligenceService(_FakePM(), target_brand="Firman")


def _collected():
    return {
        "Product Intelligence": [
            ("What generators do you recommend for home backup?",
             "Generac and Kohler dominate home standby. Firman is not typically "
             "mentioned for whole-house backup systems."),
            ("What's a good portable generator?",
             "Firman and Honda both make solid portable generators."),
        ],
    }


def test_portfolio_pass_formats_prompt_without_keyerror():
    svc = _service()
    provider = _FakeProvider([
        "IN PORTFOLIO: Portable Generators\n"
        "NOT IN PORTFOLIO: Home Standby / Whole-House Backup\n"
        "UNCERTAIN: RV-Specific Generators",
    ])
    result = svc._run_portfolio_pass(provider, _collected())
    assert "NOT IN PORTFOLIO" in result
    assert len(provider.calls) == 1
    assert "Firman" in provider.calls[0]


def test_portfolio_pass_with_no_data_does_not_call_provider():
    svc = _service()
    provider = _FakeProvider([])
    result = svc._run_portfolio_pass(provider, {})
    assert provider.calls == []
    assert "No data" in result


def test_opportunity_pass_embeds_portfolio_block():
    svc = _service()
    provider = _FakeProvider([
        "OPPORTUNITY [1]: Test\nEVIDENCE: 1 of 2\nACTION: Test\nTACTICS: Test",
    ])
    portfolio_block = "NOT IN PORTFOLIO: Home Standby / Whole-House Backup"
    svc._run_opportunity_pass(provider, _collected(), portfolio_block)
    assert len(provider.calls) == 1
    assert "NOT IN PORTFOLIO" in provider.calls[0]
    assert "Home Standby" in provider.calls[0]


def test_briefing_pass_embeds_portfolio_block_and_gap_guidance():
    svc = _service()
    provider = _FakeProvider(["VISIBILITY SNAPSHOT\nTest content."])
    portfolio_block = "NOT IN PORTFOLIO: Home Standby / Whole-House Backup"
    brand_stats = svc._count_brands(_collected())
    svc._run_briefing_pass(provider, _collected(), brand_stats, portfolio_block)
    assert len(provider.calls) == 1
    sent = provider.calls[0]
    assert "NOT IN PORTFOLIO" in sent
    assert "Portfolio gap" in sent  # the GAPS AND RISKS instruction, not just the data


# ── Error handling / graceful degradation (#42) ───────────────────────────────
# A single API failure (rate limit, timeout, bad key) must not crash the whole
# Intelligence run — each pass must degrade to a visible, non-crashing result.

def test_portfolio_pass_survives_provider_failure():
    svc = _service()
    provider = _FailingProvider("rate limit exceeded")
    result = svc._run_portfolio_pass(provider, _collected())
    assert "rate limit exceeded" in result
    assert "fake" in result  # provider name included so the user knows which provider failed


def test_opportunity_pass_failure_still_produces_a_parseable_card():
    """
    A failed opportunity pass must return text that _parse_opportunities() can
    still parse into one real card — so the user sees "generation failed" as
    an actual opportunity card instead of an empty list with no explanation.
    """
    svc = _service()
    provider = _FailingProvider("invalid API key")
    result = svc._run_opportunity_pass(provider, _collected(), "IN PORTFOLIO: Portables")
    assert "invalid API key" in result

    parsed = IntelligenceService._parse_opportunities(result)
    assert len(parsed) == 1
    assert "failed" in parsed[0]["title"].lower()
    assert "invalid API key" in parsed[0]["evidence"]


def test_briefing_pass_survives_provider_failure():
    svc = _service()
    provider = _FailingProvider("connection timed out")
    brand_stats = svc._count_brands(_collected())
    result = svc._run_briefing_pass(provider, _collected(), brand_stats, "IN PORTFOLIO: Portables")
    assert "connection timed out" in result
    assert "fake" in result


def test_portfolio_pass_survives_non_raising_provider_error():
    """A provider that fails without raising (is_error=True) must degrade the
    same way as one that raises — this is the actual shape every real
    AIProvider subclass uses (see backend/ai/*_provider.py)."""
    svc = _service()
    provider = _ErroringProvider("rate limit exceeded")
    result = svc._run_portfolio_pass(provider, _collected())
    assert "rate limit exceeded" in result
    assert "fake" in result


def test_opportunity_pass_non_raising_error_still_produces_a_parseable_card():
    svc = _service()
    provider = _ErroringProvider("invalid API key")
    result = svc._run_opportunity_pass(provider, _collected(), "IN PORTFOLIO: Portables")
    assert "invalid API key" in result

    parsed = IntelligenceService._parse_opportunities(result)
    assert len(parsed) == 1
    assert "failed" in parsed[0]["title"].lower()
    assert "invalid API key" in parsed[0]["evidence"]


def test_briefing_pass_survives_non_raising_provider_error():
    svc = _service()
    provider = _ErroringProvider("connection timed out")
    brand_stats = svc._count_brands(_collected())
    result = svc._run_briefing_pass(provider, _collected(), brand_stats, "IN PORTFOLIO: Portables")
    assert "connection timed out" in result
    assert "fake" in result


def test_provider_failure_in_one_pass_does_not_prevent_others_from_running():
    """
    Simulates the real _synthesize_and_save/_run_live sequencing: portfolio
    pass fails, but its (graceful) string output must still be usable as
    portfolio_block input to the opportunity and briefing passes, which
    should run normally rather than being blocked by the earlier failure.
    """
    svc = _service()
    failing = _FailingProvider("portfolio provider down")
    portfolio_block = svc._run_portfolio_pass(failing, _collected())
    assert "portfolio provider down" in portfolio_block

    working = _FakeProvider([
        "OPPORTUNITY [1]: Test\nEVIDENCE: 1 of 2\nACTION: Test\nTACTICS: Test",
    ])
    opp_result = svc._run_opportunity_pass(working, _collected(), portfolio_block)
    assert len(working.calls) == 1
    assert "portfolio provider down" in working.calls[0]  # degraded block still passed through
    assert "OPPORTUNITY [1]: Test" in opp_result  # and the pass still completed normally

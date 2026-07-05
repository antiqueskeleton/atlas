"""
Tests for #77 — two real bugs found in the Investigation page's legacy
architecture (backend/agents/, backend/investigations/), a separate, older
code path from the Intelligence Engine that never received the same
grounding/error-handling hardening:

1. AIReasoningParser silently treated a JSON-parse failure as a successful
   response (is_error was never set), so a broken/unparseable AI response
   rendered identically to real analysis.
2. ExecutivePromptBuilder asked the LLM for "plain English" while the
   shared parser always attempts json.loads() — a guaranteed, deterministic
   mismatch that made the executive consensus synthesis fail every time it
   ran, with the failure masquerading as a fake 100/100-confidence result.

Also covers the RESPONSE_SCHEMA grounding rules added to address the
Firman/Yamaha fabrication (the AI stated a brand relationship that doesn't
exist, having no instruction to only use the supplied evidence).
"""
from unittest.mock import patch

from backend.ai.ai_reasoning_parser import AIReasoningParser
from backend.ai.response_schema import RESPONSE_SCHEMA
from backend.investigations.task_result import TaskResult
from backend.investigations.executive_consensus_engine import ExecutiveConsensusEngine
from backend.investigations.executive_prompt_builder import ExecutivePromptBuilder
from backend.models.ai_reasoning import AIReasoning
from backend.agents.competitive_position_agent import CompetitivePositionAgent
from backend.agents.feature_comparison_agent import FeatureComparisonAgent
from backend.agents.customer_sentiment_agent import CustomerSentimentAgent
from backend.agents.strategic_opportunities_agent import StrategicOpportunitiesAgent


# ── AIReasoningParser ────────────────────────────────────────────────────────

def test_parser_sets_is_error_false_on_valid_json():
    parser = AIReasoningParser()
    reasoning = parser.parse(
        '{"executive_summary": "Test", "confidence": "High"}', provider="OpenAI",
    )
    assert reasoning.is_error is False


def test_parser_sets_is_error_true_on_invalid_json():
    parser = AIReasoningParser()
    reasoning = parser.parse("This is plain English, not JSON at all.", provider="OpenAI")
    assert reasoning.is_error is True
    assert reasoning.confidence == "Low"
    assert reasoning.raw_response == "This is plain English, not JSON at all."


# ── RESPONSE_SCHEMA grounding rules ──────────────────────────────────────────

def test_response_schema_includes_grounding_rules():
    assert "Grounding rules" in RESPONSE_SCHEMA
    assert "outside facts about corporate ownership" in RESPONSE_SCHEMA


# ── ExecutivePromptBuilder ───────────────────────────────────────────────────

def test_executive_prompt_no_longer_asks_for_plain_english():
    prompt = ExecutivePromptBuilder().build([
        TaskResult(task="Competitive Positioning", summary="Test summary", confidence="High"),
    ])
    assert "plain English" not in prompt


def test_executive_prompt_includes_response_schema_so_parser_will_succeed():
    prompt = ExecutivePromptBuilder().build([
        TaskResult(task="Competitive Positioning", summary="Test summary", confidence="High"),
    ])
    assert "Return ONLY valid JSON" in prompt
    assert '"executive_summary"' in prompt


def test_executive_prompt_still_includes_agent_findings():
    prompt = ExecutivePromptBuilder().build([
        TaskResult(task="Customer Sentiment", summary="Users like the price.", confidence="Medium"),
    ])
    assert "Customer Sentiment" in prompt
    assert "Users like the price." in prompt


# ── Agents thread is_error through from AIReasoning to TaskResult ──────────

class _FakePM:
    def get_provider(self, name):
        return None


def _agent_reasoning(is_error, executive_summary="Test finding"):
    return AIReasoning(
        executive_summary=executive_summary, confidence="High",
        provider="OpenAI", is_error=is_error,
    )


def test_competitive_position_agent_propagates_is_error():
    agent = CompetitivePositionAgent()
    with patch("backend.agents.agent_ai_service.AgentAIService.ask",
               return_value=_agent_reasoning(is_error=True)):
        result = agent.run(analysis={"summary": object()}, request=object(), provider_manager=_FakePM())
    assert result.is_error is True


def test_feature_comparison_agent_propagates_is_error_false_on_success():
    agent = FeatureComparisonAgent()
    with patch("backend.agents.agent_ai_service.AgentAIService.ask",
               return_value=_agent_reasoning(is_error=False)):
        result = agent.run(analysis={"summary": object()}, request=object(), provider_manager=_FakePM())
    assert result.is_error is False


def test_customer_sentiment_agent_propagates_is_error():
    agent = CustomerSentimentAgent()
    with patch("backend.agents.agent_ai_service.AgentAIService.ask",
               return_value=_agent_reasoning(is_error=True)):
        result = agent.run(analysis={"summary": object()}, request=object(), provider_manager=_FakePM())
    assert result.is_error is True


def test_strategic_opportunities_agent_propagates_is_error():
    agent = StrategicOpportunitiesAgent()
    with patch("backend.agents.agent_ai_service.AgentAIService.ask",
               return_value=_agent_reasoning(is_error=True)):
        result = agent.run(analysis={"summary": object()}, request=object(), provider_manager=_FakePM())
    assert result.is_error is True


# ── ExecutiveConsensusEngine ─────────────────────────────────────────────────

class _FakeProvider:
    def __init__(self, reasoning):
        self._reasoning = reasoning

    def ask(self, prompt, context=None):
        return self._reasoning


class _FakeProviderManager:
    def __init__(self, reasoning):
        self._reasoning = reasoning

    def get_active_provider(self):
        return _FakeProvider(self._reasoning)


def _task_result(task="Competitive Positioning", confidence="High", is_error=False):
    return TaskResult(task=task, summary="A real finding.", confidence=confidence, is_error=is_error)


def test_is_error_results_excluded_from_completed_and_agreement():
    task_results = [
        _task_result("Competitive Positioning", "High", is_error=False),
        _task_result("Strategic Opportunities", "Low", is_error=True),
    ]
    consensus = ExecutiveConsensusEngine().generate(task_results, provider_manager=None)
    assert len(consensus.areas_of_agreement) == 1
    assert "Strategic Opportunities" not in consensus.areas_of_agreement[0]
    # confidence_score in the rule-based path only reflects the 1 real result
    assert consensus.confidence_score == min(100, 25 + 10)


def test_synthesis_failure_falls_back_to_rule_based_not_fake_success():
    """
    The core #77 regression test: a parse-failure AIReasoning (is_error=True)
    must NOT produce a fake high-confidence consensus from garbage content —
    it must fall through to the honest rule-based path, same as a raised
    exception.
    """
    broken_reasoning = AIReasoning(
        executive_summary="Summary of Findings:\n\nAgreement: ...\n\nAtlas Confidence Score: 100/100",
        confidence="Low",
        risks=["The provider returned text that could not be parsed into Atlas reasoning."],
        opportunities=["Review the raw AI response. It was not valid JSON."],
        provider="OpenAI",
        is_error=True,
    )
    task_results = [_task_result("Competitive Positioning", "High")]
    pm = _FakeProviderManager(broken_reasoning)

    consensus = ExecutiveConsensusEngine().generate(task_results, provider_manager=pm)

    # Must be the rule-based fallback text, NOT the broken raw LLM prose.
    assert "Atlas reviewed" in consensus.overall_read
    assert "Summary of Findings" not in consensus.overall_read
    assert "could not be parsed into Atlas reasoning" not in consensus.key_risks
    assert "Review the raw AI response" not in consensus.recommended_actions
    # Confidence score must come from the honest rule-based formula, not a
    # value that implies the LLM synthesis actually worked.
    assert consensus.confidence_score == min(100, (1 * 25) + (1 * 10))


def test_successful_synthesis_still_uses_llm_output():
    good_reasoning = AIReasoning(
        executive_summary="Firman should focus on affordable pricing.",
        confidence="High",
        risks=["Competitors have stronger brand recognition."],
        opportunities=["Emphasize value pricing in marketing."],
        provider="OpenAI",
        is_error=False,
    )
    task_results = [_task_result("Competitive Positioning", "High")]
    pm = _FakeProviderManager(good_reasoning)

    consensus = ExecutiveConsensusEngine().generate(task_results, provider_manager=pm)

    assert consensus.overall_read == "Firman should focus on affordable pricing."
    assert consensus.key_risks == ["Competitors have stronger brand recognition."]
    assert consensus.recommended_actions == ["Emphasize value pricing in marketing."]


def test_raised_exception_still_falls_back_to_rule_based():
    class _RaisingProvider:
        def ask(self, prompt, context=None):
            raise RuntimeError("API timeout")

    class _RaisingPM:
        def get_active_provider(self):
            return _RaisingProvider()

    task_results = [_task_result("Competitive Positioning", "High")]
    consensus = ExecutiveConsensusEngine().generate(task_results, provider_manager=_RaisingPM())

    assert "Atlas reviewed" in consensus.overall_read


def test_no_provider_manager_uses_rule_based_directly():
    task_results = [_task_result("Competitive Positioning", "High")]
    consensus = ExecutiveConsensusEngine().generate(task_results, provider_manager=None)
    assert "Atlas reviewed" in consensus.overall_read


def test_all_results_erroring_produces_no_completed_findings_message():
    task_results = [_task_result("Competitive Positioning", "Low", is_error=True)]
    consensus = ExecutiveConsensusEngine().generate(task_results, provider_manager=None)
    assert consensus.overall_read == "No completed agent findings are available for consensus."

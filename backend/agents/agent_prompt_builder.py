from backend.agents.agent_evidence_selector import AgentEvidenceSelector
from backend.agents.prompts import (
    COMPETITIVE_POSITION_PROMPT,
    FEATURE_COMPARISON_PROMPT,
    CUSTOMER_SENTIMENT_PROMPT,
    STRATEGIC_OPPORTUNITIES_PROMPT,
)
from backend.ai.response_schema import RESPONSE_SCHEMA


class AgentPromptBuilder:

    def __init__(self):
        self.evidence_selector = AgentEvidenceSelector()

    def build(self, task_name, request, analysis):
        summary = analysis["summary"]

        prompts = {
            "Competitive Positioning": COMPETITIVE_POSITION_PROMPT,
            "Feature Comparison": FEATURE_COMPARISON_PROMPT,
            "Customer Sentiment": CUSTOMER_SENTIMENT_PROMPT,
            "Strategic Opportunities": STRATEGIC_OPPORTUNITIES_PROMPT,
        }

        specialist_prompt = prompts.get(
            task_name,
            "You are an Atlas investigation specialist."
        )

        evidence_items = self.evidence_selector.select(
            task_name,
            analysis,
            limit=6
        )

        evidence_text = "\n\n".join(
            f"{index + 1}. Source: {item.source}\n"
            f"Prompt: {item.prompt}\n"
            f"Excerpt: {item.text[:500]}"
            for index, item in enumerate(evidence_items)
        )

        return f"""
{specialist_prompt}

Business Question:
{request.question}

Intent:
{request.intent}

Target Brand:
{request.target_brand}

Competitor:
{request.competitor}

Target Feature:
{request.target_feature}

Dataset Summary:
Responses: {summary.evidence_count}
Brand Signals: {summary.finding_counts_by_type.get("brand", 0)}
Feature Signals: {summary.finding_counts_by_type.get("feature", 0)}

Relevant Supporting Evidence (highest ranked first):
{evidence_text}

{RESPONSE_SCHEMA}
""".strip()
from backend.ai.response_schema import RESPONSE_SCHEMA

class PromptBuilder:
    def build(self, request, analysis):
        summary = analysis["summary"]
        evidence_items = analysis.get("evidence", [])[:8]
        relationships = analysis.get("relationships", [])[:12]

        evidence_text = "\n\n".join(
            f"{index + 1}. Source: {item.source}\n"
            f"Prompt: {item.prompt}\n"
            f"Excerpt: {item.text[:500]}"
            for index, item in enumerate(evidence_items)
        )

        relationship_text = "\n".join(
            f"- {relationship.source} → {relationship.target}"
            for relationship in relationships
        )

        prompt = f"""
You are Atlas, an AI Competitive Intelligence Analyst.

Use ONLY the supplied Atlas dataset evidence.
Do not use outside knowledge unless explicitly asked.

Business Question:
{request.question}

Interpreted Request:
Intent: {request.intent}
Target Brand: {request.target_brand}
Competitor: {request.competitor}
Target Feature: {request.target_feature}

Dataset Summary:
Responses: {summary.evidence_count}
Brands Found: {summary.finding_counts_by_type.get("brand", 0)}
Features Found: {summary.finding_counts_by_type.get("feature", 0)}

Supporting Evidence:
{evidence_text}

Relationship Signals:
{relationship_text}

{RESPONSE_SCHEMA}
"""

        return prompt.strip()
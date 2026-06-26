class PromptBuilder:
    def build(self, request, analysis):
        summary = analysis["summary"]

        prompt = f"""
You are Atlas, an AI Competitive Intelligence Analyst.

Business Question:
{request.question}

Dataset Summary:
Responses: {summary.evidence_count}

Brands Found:
{summary.finding_counts_by_type.get("brand", 0)}

Features Found:
{summary.finding_counts_by_type.get("feature", 0)}

Instructions:

Use ONLY the supplied dataset.

Explain your reasoning.

Provide:
1. Executive Summary
2. Opportunities
3. Risks
4. Follow-Up Questions
"""

        return prompt.strip()
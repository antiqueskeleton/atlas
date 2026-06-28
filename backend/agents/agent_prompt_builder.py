from backend.ai.response_schema import RESPONSE_SCHEMA


class AgentPromptBuilder:

    def build(self, task_name, request, analysis):
        summary = analysis["summary"]

        return f"""
You are an Atlas specialist agent.

Agent Task:
{task_name}

Business Question:
{request.question}

Dataset Summary:
Responses: {summary.evidence_count}
Brand Signals: {summary.finding_counts_by_type.get("brand", 0)}
Feature Signals: {summary.finding_counts_by_type.get("feature", 0)}

Focus only on your assigned task.

{RESPONSE_SCHEMA}
""".strip()
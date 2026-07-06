from backend.agents.base_agent import BaseAgent
from backend.agents.agent_ai_service import AgentAIService
from backend.investigations.task_result import TaskResult


class CustomerSentimentAgent(BaseAgent):

    @property
    def task_name(self):
        return "Customer Sentiment"

    def run(self, analysis, request=None, provider_manager=None):
        if analysis is None:
            return TaskResult(
                task=self.task_name,
                summary="No active dataset is available to evaluate customer sentiment.",
                confidence="Low"
            )

        if request is not None and provider_manager is not None:
            reasoning = AgentAIService(provider_manager).ask(
                self.task_name,
                request,
                analysis
            )

            return TaskResult(
                task=self.task_name,
                summary=reasoning.executive_summary,
                confidence=reasoning.confidence,
                provider=reasoning.provider,
                raw_response=reasoning.raw_response,
                # #80: is_error here means "not trustworthy for synthesis" —
                # either a real request failure OR a response that didn't
                # come back as the structured JSON this agent asked for.
                is_error=reasoning.is_error or reasoning.parse_failed,
            )

        summary = analysis["summary"]

        return TaskResult(
            task=self.task_name,
            summary=(
                f"Customer Sentiment analyzed {summary.evidence_count} responses. "
                f"Atlas found {summary.finding_counts_by_type.get('brand', 0)} brand signals "
                f"and {summary.finding_counts_by_type.get('feature', 0)} feature signals."
            ),
            confidence="Medium"
        )
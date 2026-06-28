from backend.agents.base_agent import BaseAgent
from backend.agents.agent_ai_service import AgentAIService
from backend.investigations.task_result import TaskResult


class CompetitivePositionAgent(BaseAgent):

    @property
    def task_name(self):
        return "Competitive Positioning"

    def run(self, analysis, request=None, provider_manager=None):
        if analysis is None:
            return TaskResult(
                task=self.task_name,
                summary="No active dataset is available for competitive positioning analysis.",
                confidence="Low"
            )

        if request is None:
            summary = analysis["summary"]

            return TaskResult(
                task=self.task_name,
                summary=(
                    f"Competitive Positioning analyzed {summary.evidence_count} responses. "
                    f"Atlas found {summary.finding_counts_by_type.get('brand', 0)} brand signals "
                    f"and {summary.finding_counts_by_type.get('feature', 0)} feature signals."
                ),
                confidence="Medium"
            )

        ai_service = AgentAIService(request.provider_manager) if hasattr(request, "provider_manager") else None

        summary = analysis["summary"]

        return TaskResult(
            task=self.task_name,
            summary=(
                f"Competitive Positioning analyzed {summary.evidence_count} responses. "
                f"Atlas found {summary.finding_counts_by_type.get('brand', 0)} brand signals "
                f"and {summary.finding_counts_by_type.get('feature', 0)} feature signals. "
                f"AI-enabled agent framework is ready for provider-backed competitive analysis."
            ),
            confidence="Medium"
        )
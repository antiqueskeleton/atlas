from backend.investigations.task_result import TaskResult
from backend.agents.base_agent import BaseAgent
from backend.agents.base_agent import BaseAgent


class CompetitivePositionAgent(BaseAgent):
    @property
    def task_name(self):
        return "Competitive Positioning"

    def run(self, analysis, request=None):
        if analysis is None:
            return TaskResult(
                task="Competitive Positioning",
                summary="No active dataset is available for competitive positioning analysis.",
                confidence="Low"
            )

        summary = analysis["summary"]

        result = (
            f"Competitive Positioning analyzed {summary.evidence_count} responses. "
            f"Atlas found {summary.finding_counts_by_type.get('brand', 0)} brand signals "
            f"and {summary.finding_counts_by_type.get('feature', 0)} feature signals. "
            f"This provides the foundation for comparing brand visibility, feature association, "
            f"and competitive positioning."
        )

        return TaskResult(
            task="Competitive Positioning",
            summary=result,
            confidence="Medium"
        )
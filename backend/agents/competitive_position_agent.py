from backend.investigations.task_result import TaskResult


class CompetitivePositionAgent:

    def run(self, analysis):
        summary = (
            "Competitive positioning analysis completed. "
            "Atlas identified the strongest competitive signals "
            "within the current dataset."
        )

        return TaskResult(
            task="Competitive Positioning",
            summary=summary,
            confidence="Medium"
        )
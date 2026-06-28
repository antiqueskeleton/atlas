from backend.investigations.task_result import TaskResult


class InvestigationExecutor:
    def execute(self, plan):
        results = []

        for task in plan.tasks:
            results.append(
                TaskResult(
                    task=task,
                    summary=f"{task} analysis completed.",
                    confidence="Pending"
                )
            )

        return results
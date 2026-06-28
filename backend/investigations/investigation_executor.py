from backend.agents.competitive_position_agent import CompetitivePositionAgent
from backend.investigations.task_result import TaskResult


class InvestigationExecutor:

    def __init__(self):
        self.competitive_agent = CompetitivePositionAgent()

    def execute(self, plan, analysis):
        results = []

        for task in plan.tasks:

            if task == "Competitive Positioning":
                results.append(
                    self.competitive_agent.run(analysis)
                )
            else:
                results.append(
                    TaskResult(
                        task=task,
                        summary=f"{task} analysis is not implemented yet.",
                        confidence="Pending"
                    )
                )

        return results
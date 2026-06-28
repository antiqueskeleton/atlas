from backend.agents.agent_registry import AgentRegistry
from backend.investigations.task_result import TaskResult


class InvestigationExecutor:

    def __init__(self):
        self.agents = AgentRegistry.build()

    def execute(self, plan, analysis):
        results = []

        for task in plan.tasks:

            agent = self.agents.get(task)

            if agent:
                results.append(
                    agent.run(analysis)
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
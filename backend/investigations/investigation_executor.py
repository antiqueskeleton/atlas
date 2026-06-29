from backend.agents.agent_registry import AgentRegistry
from backend.investigations.task_result import TaskResult


class InvestigationExecutor:

    def __init__(self, provider_manager=None):
        self.agents = AgentRegistry.build()
        self.provider_manager = provider_manager

    def execute(self, plan, analysis, request=None, progress_callback=None):
        results = []
        total = len(plan.tasks)

        for i, task in enumerate(plan.tasks):
            if progress_callback:
                progress_callback(task, i + 1, total)

            agent = self.agents.get(task)

            if agent:
                results.append(
                    agent.run(analysis, request, self.provider_manager)
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
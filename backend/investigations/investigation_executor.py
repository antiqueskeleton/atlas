import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.agents.agent_registry import AgentRegistry
from backend.investigations.task_result import TaskResult


class InvestigationExecutor:

    def __init__(self, provider_manager=None):
        self.agents = AgentRegistry.build()
        self.provider_manager = provider_manager

    def execute(self, plan, analysis, request=None, progress_callback=None):
        tasks = plan.tasks
        total = len(tasks)
        results = [None] * total  # preserve original task order
        completed = [0]
        lock = threading.Lock()

        def _run_task(idx: int, task: str):
            agent = self.agents.get(task)
            if agent:
                result = agent.run(analysis, request, self.provider_manager)
            else:
                result = TaskResult(
                    task=task,
                    summary=f"{task} analysis is not implemented yet.",
                    confidence="Pending",
                )
            results[idx] = result
            with lock:
                completed[0] += 1
                done = completed[0]
            if progress_callback:
                progress_callback(task, done, total)
            return idx

        with ThreadPoolExecutor(max_workers=min(total, 6)) as pool:
            futures = {pool.submit(_run_task, i, task): i for i, task in enumerate(tasks)}
            for future in as_completed(futures):
                future.result()  # re-raise any unexpected exception

        return results

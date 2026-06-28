from backend.investigations.task_result import TaskResult


class CompShopAgent:

    def run(self, analysis):
        if analysis is None:
            return TaskResult(
                task="Comp Shop",
                summary="No active dataset is available for comparison.",
                confidence="Low"
            )

        summary = (
            "Comp Shop analysis framework is ready. "
            "Atlas will compare Firman products against competitor products "
            "using product features, positioning, pricing, customer needs, "
            "and AI visibility signals."
        )

        return TaskResult(
            task="Comp Shop",
            summary=summary,
            confidence="Pending"
        )
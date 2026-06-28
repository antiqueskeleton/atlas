from backend.investigations.task_result import TaskResult


class CustomerSentimentAgent:

    def run(self, analysis, request=None, provider_manager=None):
        if analysis is None:
            return TaskResult(
                task="Customer Sentiment",
                summary="No active dataset is available to evaluate customer sentiment.",
                confidence="Low"
            )

        summary = analysis["summary"]

        result = (
            f"Customer Sentiment analyzed {summary.evidence_count} responses. "
            f"Atlas found {summary.finding_counts_by_type.get('brand', 0)} brand signals "
            f"and {summary.finding_counts_by_type.get('feature', 0)} feature signals. "
            f"This can help identify positive perception, negative perception, recurring complaints, "
            f"and preference signals across the dataset."
        )

        return TaskResult(
            task="Customer Sentiment",
            summary=result,
            confidence="Medium"
        )
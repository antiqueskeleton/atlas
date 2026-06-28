from backend.investigations.task_result import TaskResult


class CustomerSentimentAgent:

    def run(self, analysis, request=None):
        if analysis is None:
            return TaskResult(
                task="Customer Sentiment",
                summary="No active dataset is available to evaluate customer sentiment.",
                confidence="Low"
            )

        summary = (
            "Customer Sentiment framework is ready. "
            "Atlas will evaluate how customers, AI responses, or source materials describe "
            "brand perception, product strengths, weaknesses, complaints, and preference signals."
        )

        return TaskResult(
            task="Customer Sentiment",
            summary=summary,
            confidence="Medium"
        )
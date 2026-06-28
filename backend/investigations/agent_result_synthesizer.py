class AgentResultSynthesizer:

    def synthesize(self, task_results):
        if not task_results:
            return "No agent task results are available."

        completed = [
            result for result in task_results
            if result.confidence != "Pending"
        ]

        if not completed:
            return "Agent tasks were created, but no completed agent results are available yet."

        text = "Agent Findings Summary:\n\n"

        for result in completed:
            text += (
                f"{result.task}\n"
                f"Confidence: {result.confidence}\n"
                f"{result.summary}\n\n"
            )

        return text.strip()
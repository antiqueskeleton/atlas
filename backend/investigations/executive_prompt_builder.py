class ExecutivePromptBuilder:

    def build(self, task_results):
        prompt = """
You are Atlas's Executive Intelligence Officer.

You have received reports from multiple specialist AI analysts.

Your job is to:

• Find agreement
• Identify conflicts
• Determine overall confidence
• Produce executive recommendations

Return plain English.

""".strip()

        prompt += "\n\nAgent Findings:\n\n"

        for result in task_results:

            prompt += (
                f"{result.task}\n"
                f"Confidence: {result.confidence}\n"
                f"{result.summary}\n\n"
            )

        return prompt
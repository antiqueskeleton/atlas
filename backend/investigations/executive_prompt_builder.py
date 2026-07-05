from backend.ai.response_schema import RESPONSE_SCHEMA


class ExecutivePromptBuilder:

    def build(self, task_results):
        # #77 fix: this previously ended with "Return plain English." while
        # the shared AIReasoningParser always attempts json.loads() on the
        # response — a guaranteed, deterministic mismatch that made this
        # synthesis step fail every single time it ran against a real
        # provider (the parse failure then rendered as if it were a real,
        # high-confidence executive consensus — see #77's root-cause notes).
        # Now requests the SAME structured JSON schema every agent already
        # uses, so the parser actually succeeds, and so the same grounding
        # rules in RESPONSE_SCHEMA apply to this synthesis step too.
        prompt = """
You are Atlas's Executive Intelligence Officer.

You have received reports from multiple specialist AI analysts, each already
grounded in real evidence from Atlas's dataset. Your job is to synthesize
their findings — do NOT introduce new claims of your own.

Your job is to:

• Find agreement across the analysts' findings below
• Identify conflicts between the analysts' findings below
• Determine overall confidence in the synthesized view
• Produce executive recommendations that follow directly from the findings below

Put the synthesized narrative in executive_summary. Put agreements and
recommendations in opportunities. Put conflicts and open questions in risks.
""".strip()

        prompt += "\n\nAgent Findings:\n\n"

        for result in task_results:

            prompt += (
                f"{result.task}\n"
                f"Confidence: {result.confidence}\n"
                f"{result.summary}\n\n"
            )

        prompt += f"\n{RESPONSE_SCHEMA}"

        return prompt
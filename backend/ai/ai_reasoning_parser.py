from backend.models.ai_reasoning import AIReasoning


class AIReasoningParser:
    def parse(self, text: str, provider: str) -> AIReasoning:
        return AIReasoning(
            executive_summary=text,
            confidence="Medium",
            opportunities=[
                "Review the AI-generated answer against Atlas evidence."
            ],
            risks=[
                "Live AI reasoning should be validated before business decisions."
            ],
            follow_up_questions=[
                "What evidence supports this?",
                "How would another provider answer?",
            ],
            provider=provider,
        )
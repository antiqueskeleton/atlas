import json

from backend.models.ai_reasoning import AIReasoning


class AIReasoningParser:
    def parse(self, text: str, provider: str) -> AIReasoning:
        try:
            data = json.loads(text)

            return AIReasoning(
                executive_summary=data.get("executive_summary", ""),
                confidence=data.get("confidence", "Medium"),
                raw_response=text,
                opportunities=data.get("opportunities", []),
                risks=data.get("risks", []),
                follow_up_questions=data.get("follow_up_questions", []),
                provider=provider,
            )

        except Exception:
            return AIReasoning(
                executive_summary=text,
                confidence="Low",
                raw_response=text,
                opportunities=[
                    "Review the raw AI response. It was not valid JSON."
                ],
                risks=[
                    "The provider returned text that could not be parsed into Atlas reasoning."
                ],
                follow_up_questions=[
                    "Should Atlas retry with stricter JSON instructions?"
                ],
                provider=provider,
            )
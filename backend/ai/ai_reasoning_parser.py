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
                supporting_evidence=data.get("supporting_evidence", []),
                follow_up_questions=data.get("follow_up_questions", []),
                provider=provider,
            )

        except Exception:
            # is_error=True is the critical part here — without it, this parse
            # failure is indistinguishable from a real, successful response to
            # any caller that only looks at executive_summary/risks/opportunities
            # (which is exactly what let a broken response render as a fake
            # high-confidence "executive consensus" — see #77).
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
                supporting_evidence=[],
                follow_up_questions=[
                    "Should Atlas retry with stricter JSON instructions?"
                ],
                provider=provider,
                is_error=True,
            )
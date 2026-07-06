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
            # IMPORTANT: this is NOT necessarily an error. This same parser is
            # shared by every provider's ask(), used both by Visibility
            # Collection (plain conversational prompts, NEVER asking for
            # JSON — a normal plain-text answer legitimately fails
            # json.loads() every time, and that is completely expected) and
            # the Investigation page's agents (which DO explicitly request
            # JSON via RESPONSE_SCHEMA, where a parse failure is a real
            # problem). is_error must stay False here — a prior version of
            # this code set is_error=True unconditionally, which silently
            # broke Visibility Collection for every provider (every normal
            # plain-text response got marked an error and never saved) — see
            # #80. parse_failed is the signal callers that DO expect JSON
            # (executive_consensus_engine.py, the 4 live-AI agents) should
            # check instead.
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
                parse_failed=True,
            )
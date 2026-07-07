from dataclasses import dataclass, field


@dataclass
class AIReasoning:
    executive_summary: str
    confidence: str = "Unknown"
    opportunities: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    follow_up_questions: list[str] = field(default_factory=list)
    supporting_evidence: list[int] = field(default_factory=list)
    provider: str = ""
    raw_response: str = ""
    is_error: bool = False
    # parse_failed: the response wasn't valid JSON. Deliberately separate from
    # is_error — a caller that never asked for JSON (Visibility Collection
    # sends plain conversational prompts) gets a perfectly valid plain-text
    # answer here, which must NOT be treated as an error. Only callers that
    # explicitly requested structured JSON (the Investigation page's agents,
    # via RESPONSE_SCHEMA) should treat parse_failed as a real problem.
    parse_failed: bool = False
    # Source URLs the provider itself reported grounding this answer on
    # (#96) — currently populated by Perplexity (its API returns them with
    # every response); empty for providers that don't expose citations.
    citations: list[str] = field(default_factory=list)
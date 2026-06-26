from dataclasses import dataclass, field


@dataclass
class AIReasoning:
    executive_summary: str

    confidence: str = "Unknown"

    opportunities: list[str] = field(default_factory=list)

    risks: list[str] = field(default_factory=list)

    follow_up_questions: list[str] = field(default_factory=list)

    provider: str = ""
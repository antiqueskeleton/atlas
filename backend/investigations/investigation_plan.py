from dataclasses import dataclass, field


@dataclass
class InvestigationPlan:
    question: str
    tasks: list[str] = field(default_factory=list)
from dataclasses import dataclass, field


@dataclass
class ExecutiveConsensus:
    overall_read: str
    areas_of_agreement: list[str] = field(default_factory=list)
    key_risks: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
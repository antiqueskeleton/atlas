from dataclasses import dataclass


@dataclass
class InvestigationStatus:
    current_step: str
    progress: int
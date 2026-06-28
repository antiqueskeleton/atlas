from dataclasses import dataclass


@dataclass
class TaskResult:
    task: str
    summary: str
    confidence: str
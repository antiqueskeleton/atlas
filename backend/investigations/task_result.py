from dataclasses import dataclass


@dataclass
class TaskResult:
    task: str
    summary: str
    confidence: str
    provider: str = ""
    raw_response: str = ""
    is_error: bool = False
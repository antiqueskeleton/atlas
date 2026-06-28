from dataclasses import dataclass


@dataclass
class PromptResult:
    prompt: str
    response: str
    provider: str
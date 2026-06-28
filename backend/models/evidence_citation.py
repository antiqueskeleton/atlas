from dataclasses import dataclass


@dataclass
class EvidenceCitation:
    number: int
    source: str
    prompt: str
    preview: str
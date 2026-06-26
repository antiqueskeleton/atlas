import json
from pathlib import Path
from typing import List

from backend.models.evidence import Evidence


class EvidenceService:
    def __init__(self):
        self.project_root = Path(__file__).resolve().parents[2]

    def load_responses(self, file_path: str = "sample_data/responses/sample_responses.json") -> List[Evidence]:
        path = self.project_root / file_path

        with path.open("r", encoding="utf-8") as file:
            records = json.load(file)

        return [
            Evidence(
                evidence_id=record["evidence_id"],
                source=record["source"],
                prompt=record["prompt"],
                text=record["text"],
                metadata=record.get("metadata", {})
            )
            for record in records
        ]
import json
from pathlib import Path
from typing import List

from backend.models.evidence import Evidence
from backend.services.config_service import ConfigService


class EvidenceService:
    def __init__(self):
        self.project_root = Path(__file__).resolve().parents[2]
        self.config = ConfigService()

    def load_responses(self, file_path: str | None = None) -> List[Evidence]:
        response_file = file_path or self.config.get(
            "default_response_file",
            "sample_data/responses/sample_responses.json"
        )

        path = Path(response_file)

        if not path.is_absolute():
            path = self.project_root / path

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
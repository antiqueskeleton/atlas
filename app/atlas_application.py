from datetime import datetime
from pathlib import Path

from backend.services.knowledge_service import KnowledgeService
from backend.services.evidence_service import EvidenceService
from backend.registry.analyst_registry import AnalystRegistry
from backend.engines.insight_engine import InsightEngine
from backend.engines.relationship_engine import RelationshipEngine
from backend.models.run_summary import RunSummary
from backend.models.dataset import Dataset


class AtlasApplication:
    def __init__(self):
        self.current_dataset = None
        self.current_results = []
        self.current_summary = None
        self.current_insights = []
        self.current_relationships = []

    def analyze(self, response_file=None):
        knowledge_service = KnowledgeService()
        evidence_service = EvidenceService()

        knowledge = {
            "brands": knowledge_service.get_brands(),
            "features": knowledge_service.get_features(),
        }

        evidence = evidence_service.load_responses(response_file)

        dataset_name = "Default Sample Dataset"

        if response_file:
            dataset_name = Path(response_file).stem.replace("_", " ").title()

        self.current_dataset = Dataset(
            name=dataset_name,
            source="JSON Import" if response_file else "Default Sample",
            imported_at=datetime.now(),
            evidence=evidence,
        )

        analysts = AnalystRegistry.get_analysts(knowledge)

        self.current_results = []

        for item in self.current_dataset.evidence:
            for analyst in analysts:
                self.current_results.append(analyst.analyze(item))

        self.current_summary = RunSummary(
            evidence_count=self.current_dataset.response_count,
            analyst_count=len(analysts),
            results=self.current_results
        ).build()

        insight_engine = InsightEngine()
        self.current_insights = insight_engine.generate(self.current_results)

        relationship_engine = RelationshipEngine()
        self.current_relationships = relationship_engine.generate(self.current_results)

        return {
            "dataset": self.current_dataset,
            "summary": self.current_summary,
            "insights": self.current_insights,
            "relationships": self.current_relationships,
            "results": self.current_results,
            "evidence": self.current_dataset.evidence,
        }

    def has_analysis(self):
        return self.current_summary is not None
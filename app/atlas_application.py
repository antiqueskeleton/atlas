from backend.services.knowledge_service import KnowledgeService
from backend.services.evidence_service import EvidenceService
from backend.registry.analyst_registry import AnalystRegistry
from backend.engines.insight_engine import InsightEngine
from backend.engines.relationship_engine import RelationshipEngine
from backend.models.run_summary import RunSummary


class AtlasApplication:
    def __init__(self):
        self.current_evidence = []
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

        self.current_evidence = evidence_service.load_responses(response_file)

        analysts = AnalystRegistry.get_analysts(knowledge)

        self.current_results = []

        for evidence in self.current_evidence:
            for analyst in analysts:
                self.current_results.append(analyst.analyze(evidence))

        self.current_summary = RunSummary(
            evidence_count=len(self.current_evidence),
            analyst_count=len(analysts),
            results=self.current_results
        ).build()

        insight_engine = InsightEngine()
        self.current_insights = insight_engine.generate(self.current_results)

        relationship_engine = RelationshipEngine()
        self.current_relationships = relationship_engine.generate(self.current_results)

        return {
            "summary": self.current_summary,
            "insights": self.current_insights,
            "relationships": self.current_relationships,
            "results": self.current_results,
            "evidence": self.current_evidence,
        }

    def has_analysis(self):
        return self.current_summary is not None
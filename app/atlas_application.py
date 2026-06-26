from backend.services.knowledge_service import KnowledgeService
from backend.services.evidence_service import EvidenceService
from backend.registry.analyst_registry import AnalystRegistry
from backend.engines.insight_engine import InsightEngine
from backend.engines.relationship_engine import RelationshipEngine
from backend.models.run_summary import RunSummary


class AtlasApplication:
    def analyze(self):
        knowledge_service = KnowledgeService()
        evidence_service = EvidenceService()

        knowledge = {
            "brands": knowledge_service.get_brands(),
            "features": knowledge_service.get_features(),
        }

        evidence_items = evidence_service.load_responses()
        analysts = AnalystRegistry.get_analysts(knowledge)

        all_results = []

        for evidence in evidence_items:
            for analyst in analysts:
                all_results.append(analyst.analyze(evidence))

        summary = RunSummary(
            evidence_count=len(evidence_items),
            analyst_count=len(analysts),
            results=all_results
        ).build()

        insight_engine = InsightEngine()
        insights = insight_engine.generate(all_results)

        relationship_engine = RelationshipEngine()
        relationships = relationship_engine.generate(all_results)

        return {
            "summary": summary,
            "insights": insights,
            "relationships": relationships,
            "results": all_results,
        }
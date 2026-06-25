from backend.engines.insight_engine import InsightEngine
from backend.orchestrator import load_sample_evidence
from backend.registry.analyst_registry import AnalystRegistry
from backend.services.knowledge_service import KnowledgeService

knowledge_service = KnowledgeService()

knowledge = {
    "brands": knowledge_service.get_brands(),
    "features": knowledge_service.get_features(),
}

analysts = AnalystRegistry.get_analysts(knowledge)

results = []

for evidence in load_sample_evidence():
    for analyst in analysts:
        results.append(analyst.analyze(evidence))

engine = InsightEngine()

insights = engine.generate(results)

for insight in insights:
    print(f"{insight.title}: {insight.description}")
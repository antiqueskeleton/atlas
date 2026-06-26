from datetime import datetime

from backend.models.evidence import Evidence
from backend.models.run_summary import RunSummary
from backend.services.knowledge_service import KnowledgeService
from backend.registry.analyst_registry import AnalystRegistry
from backend.engines.insight_engine import InsightEngine
from backend.reporting.executive_report import ExecutiveReport
from backend.engines.relationship_engine import RelationshipEngine
from backend.models.relationship_summary import RelationshipSummary
from backend.services.evidence_service import EvidenceService


def run():
    started = datetime.now()

    print("Atlas Orchestrator")
    print("------------------")
    print(f"Started: {started}")

    knowledge_service = KnowledgeService()

    knowledge = {
        "brands": knowledge_service.get_brands(),
        "features": knowledge_service.get_features(),
    }

    evidence_service = EvidenceService()

    evidence_items = evidence_service.load_responses()
    analysts = AnalystRegistry.get_analysts(knowledge)

    all_results = []

    for evidence in evidence_items:
        print(f"\nAnalyzing evidence: {evidence.evidence_id}")

        for analyst in analysts:
            result = analyst.analyze(evidence)
            all_results.append(result)

            print(f"  {result.analyst_name}: {result.notes}")

            for finding in result.findings:
                print(
                    f"    - {finding.value} "
                    f"(rank {finding.rank}, confidence {finding.confidence})"
                )

    finished = datetime.now()
    duration = finished - started

    summary = RunSummary(
        evidence_count=len(evidence_items),
        analyst_count=len(analysts),
        results=all_results
    ).build()

    print("\nRun Summary")
    print("-----------")
    print(f"Evidence analyzed: {summary.evidence_count}")
    print(f"Analysts run: {summary.analyst_count}")
    print(f"Results produced: {len(summary.results)}")

    print("\nFindings by type")
    print("----------------")
    for finding_type, count in summary.finding_counts_by_type.items():
        print(f"{finding_type}: {count}")

    insight_engine = InsightEngine()
    insights = insight_engine.generate(all_results)

    print("\nInsights")
    print("--------")
    for insight in insights:
        print(f"{insight.title}: {insight.description}")

    report = ExecutiveReport()
    report.build(summary, insights)

    relationship_engine = RelationshipEngine()
    relationships = relationship_engine.generate(all_results)
    relationship_summary = RelationshipSummary(relationships).build()

    print("\nRelationships")
    print("-------------")
    for relationship in relationships:
        print(
            f"{relationship.source} → {relationship.target} "
            f"(confidence {relationship.confidence})"
        )

    print(f"\nFinished: {finished}")
    print(f"Duration: {duration}")

    print("\nTop Brand ↔ Feature Relationships")
    print("---------------------------------")
    for relationship, count in relationship_summary.top_relationships.items():
        print(f"{relationship}: {count}")


if __name__ == "__main__":
    run()
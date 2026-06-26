from datetime import datetime

from backend.models.evidence import Evidence
from backend.models.run_summary import RunSummary
from backend.services.knowledge_service import KnowledgeService
from backend.registry.analyst_registry import AnalystRegistry
from backend.engines.insight_engine import InsightEngine
from backend.reporting.executive_report import ExecutiveReport
from backend.engines.relationship_engine import RelationshipEngine


def load_sample_evidence():
    return [
        Evidence(
            evidence_id="ev-001",
            source="manual_test",
            prompt="Best portable generator for home backup",
            text="""
            Champion and Westinghouse are often recommended for home backup.

            Firman is a strong Dual Fuel generator with Electric Start and excellent RV Ready capability.

            Honda is known for Quiet Operation and long-term reliability.

            Champion is also recognized for Electric Start and RV Ready models.
            """
        ),
        Evidence(
            evidence_id="ev-002",
            source="manual_test",
            prompt="Best quiet generator for camping",
            text="""
            Honda and Yamaha are frequently recommended for Quiet Operation while camping.

            Firman offers excellent Dual Fuel options and Electric Start on many models.

            Champion also offers RV Ready inverter generators.
            """
        )
    ]


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

    evidence_items = load_sample_evidence()
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

    print("\nRelationships")
    print("-------------")
    for relationship in relationships:
        print(
            f"{relationship.source} → {relationship.target} "
            f"(confidence {relationship.confidence})"
        )

    print(f"\nFinished: {finished}")
    print(f"Duration: {duration}")


if __name__ == "__main__":
    run()
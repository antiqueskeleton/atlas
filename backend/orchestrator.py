from datetime import datetime

from backend.models.evidence import Evidence
from backend.services.knowledge_service import KnowledgeService
from backend.registry.analyst_registry import AnalystRegistry
from backend.models.run_summary import RunSummary


def load_sample_evidence():
    return [
        Evidence(
            evidence_id="ev-001",
            source="manual_test",
            prompt="Best portable generator for home backup",
            text="""
            Champion and Westinghouse are often recommended for home backup.
            Firman is a strong value option, especially for dual fuel buyers.
            Honda is usually considered premium, quiet, and reliable.
            """
        ),
        Evidence(
            evidence_id="ev-002",
            source="manual_test",
            prompt="Best quiet generator for camping",
            text="""
            Honda and Yamaha are frequently recommended for quiet camping use.
            Firman may be considered for value, but Honda usually leads in quiet inverter discussions.
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

    print(f"\nFinished: {finished}")
    print(f"Duration: {duration}")


if __name__ == "__main__":
    run()
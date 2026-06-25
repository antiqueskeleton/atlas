from collections import Counter

from backend.models.run_summary import RunSummary


class ExecutiveReport:

    def build(self, summary: RunSummary, insights):

        brand_counter = Counter()
        feature_counter = Counter()

        for result in summary.results:

            for finding in result.findings:

                if finding.finding_type == "brand":
                    brand_counter[finding.value] += 1

                elif finding.finding_type == "feature":
                    feature_counter[finding.value] += 1

        print()
        print("=" * 60)
        print("ATLAS EXECUTIVE INTELLIGENCE REPORT")
        print("=" * 60)

        print()
        print("Processing Summary")
        print("------------------")
        print(f"Evidence Processed : {summary.evidence_count}")
        print(f"Analysts Run       : {summary.analyst_count}")

        print()
        print("Top Brands")
        print("----------")

        for brand, count in brand_counter.most_common(5):
            print(f"{brand:<20}{count}")

        print()
        print("Top Features")
        print("------------")

        for feature, count in feature_counter.most_common(10):
            print(f"{feature:<20}{count}")

        print()
        print("Key Insights")
        print("------------")

        for insight in insights:
            print(f"• {insight.description}")

        print()
        print("=" * 60)
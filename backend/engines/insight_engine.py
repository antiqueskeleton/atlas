from collections import Counter

from backend.models.insight import Insight


class InsightEngine:

    def generate(self, analysis_results):

        brand_counter = Counter()
        feature_counter = Counter()

        for result in analysis_results:

            for finding in result.findings:

                if finding.finding_type == "brand":
                    brand_counter[finding.value] += 1

                elif finding.finding_type == "feature":
                    feature_counter[finding.value] += 1

        insights = []

        if brand_counter:

            brand, count = brand_counter.most_common(1)[0]

            insights.append(
                Insight(
                    title="Top Recommended Brand",
                    description=f"{brand} appeared {count} time(s).",
                    confidence=0.90,
                    insight_type="brand"
                )
            )

        if feature_counter:

            feature, count = feature_counter.most_common(1)[0]

            insights.append(
                Insight(
                    title="Top Mentioned Feature",
                    description=f"{feature} appeared {count} time(s).",
                    confidence=0.90,
                    insight_type="feature"
                )
            )

        return insights
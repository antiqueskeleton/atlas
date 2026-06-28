from backend.investigations.task_result import TaskResult


class FeatureComparisonAgent:

    def run(self, analysis, request=None, provider_manager=None):
        if analysis is None:
            return TaskResult(
                task="Feature Comparison",
                summary="No active dataset is available to compare features.",
                confidence="Low"
            )

        summary = analysis["summary"]
        comp_shop = request.comp_shop if request else None

        if comp_shop:
            competitors = ", ".join(comp_shop.competitor_products) or "competitor products"

            result = (
                f"Feature Comparison analyzed {summary.evidence_count} responses for "
                f"{comp_shop.firman_product} against {competitors}. "
                f"Atlas found {summary.finding_counts_by_type.get('feature', 0)} feature signals. "
                f"This supports comparison of shared strengths, missing features, and AI-visible differentiators."
            )
        else:
            result = (
                f"Feature Comparison analyzed {summary.evidence_count} responses and found "
                f"{summary.finding_counts_by_type.get('feature', 0)} feature signals. "
                f"Atlas can use these signals to compare important features, gaps, overlaps, and competitive advantages."
            )

        return TaskResult(
            task="Feature Comparison",
            summary=result,
            confidence="Medium"
        )
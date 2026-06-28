from backend.investigations.task_result import TaskResult


class FeatureComparisonAgent:

    def run(self, analysis, request=None):
        if analysis is None:
            return TaskResult(
                task="Feature Comparison",
                summary="No active dataset is available to compare features.",
                confidence="Low"
            )

        comp_shop = request.comp_shop if request else None

        if comp_shop:
            competitors = ", ".join(comp_shop.competitor_products) or "competitor products"

            summary = (
                f"Feature Comparison framework is ready for "
                f"{comp_shop.firman_product} against {competitors}. "
                f"Atlas will compare feature coverage, feature gaps, shared strengths, "
                f"differentiators, and AI-visible product advantages."
            )
        else:
            summary = (
                "Feature Comparison framework is ready. "
                "Atlas will compare important features, gaps, overlaps, and competitive advantages."
            )

        return TaskResult(
            task="Feature Comparison",
            summary=summary,
            confidence="Medium"
        )
from backend.investigations.task_result import TaskResult


class CompShopAgent:

    def run(self, analysis, request=None, provider_manager=None):
        if analysis is None:
            return TaskResult(
                task="Comp Shop",
                summary="No active dataset is available for comparison.",
                confidence="Low"
            )

        summary = analysis["summary"]
        comp_shop = request.comp_shop if request else None

        if not comp_shop:
            return TaskResult(
                task="Comp Shop",
                summary="No specific comp shop request was detected.",
                confidence="Low"
            )

        competitors = ", ".join(comp_shop.competitor_products) or "competitor products"
        category = comp_shop.category or "the selected product category"

        result = (
            f"Comp Shop analyzed {summary.evidence_count} responses for "
            f"{comp_shop.target_product} against {competitors} in {category}. "
            f"Atlas found {summary.finding_counts_by_type.get('brand', 0)} brand signals "
            f"and {summary.finding_counts_by_type.get('feature', 0)} feature signals. "
            f"This supports product-to-product comparison across features, positioning, "
            f"pricing, customer fit, and AI visibility."
        )

        return TaskResult(
            task="Comp Shop",
            summary=result,
            confidence="Medium"
        )
from backend.investigations.task_result import TaskResult


class CompShopAgent:

    def run(self, analysis, request=None):
        if analysis is None:
            return TaskResult(
                task="Comp Shop",
                summary="No active dataset is available for comparison.",
                confidence="Low"
            )

        comp_shop = request.comp_shop if request else None

        if not comp_shop:
            return TaskResult(
                task="Comp Shop",
                summary="No specific comp shop request was detected.",
                confidence="Low"
            )

        competitors = ", ".join(comp_shop.competitor_products) or "competitor products"
        category = comp_shop.category or "the selected product category"

        summary = (
            f"Comp Shop framework detected a comparison request for "
            f"{comp_shop.firman_product} against {competitors} in {category}. "
            f"Atlas can use this structure to compare features, positioning, pricing, "
            f"AI visibility, and customer-fit signals."
        )

        return TaskResult(
            task="Comp Shop",
            summary=summary,
            confidence="Medium"
        )
from backend.investigations.task_result import TaskResult


class CustomerFitAgent:

    def run(self, analysis, request=None, provider_manager=None):
        if analysis is None:
            return TaskResult(
                task="Customer Fit",
                summary="No active dataset is available to evaluate customer fit.",
                confidence="Low"
            )

        comp_shop = request.comp_shop if request else None

        if comp_shop:
            competitors = ", ".join(comp_shop.competitor_products) or "competitor products"
            category = comp_shop.category or "the selected category"

            summary = (
                f"Customer Fit analysis framework is ready for "
                f"{comp_shop.target_product} against {competitors} in {category}. "
                f"Atlas will evaluate which product better matches customer needs, "
                f"use case, feature expectations, and positioning."
            )
        else:
            summary = (
                "Customer Fit analysis framework is ready. "
                "Atlas will evaluate how well the product or brand aligns with customer needs."
            )

        return TaskResult(
            task="Customer Fit",
            summary=summary,
            confidence="Medium"
        )
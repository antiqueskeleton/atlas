from backend.investigations.task_result import TaskResult


class StrategicOpportunitiesAgent:

    def run(self, analysis, request=None):
        if analysis is None:
            return TaskResult(
                task="Strategic Opportunities",
                summary="No active dataset is available to identify strategic opportunities.",
                confidence="Low"
            )

        comp_shop = request.comp_shop if request else None

        if comp_shop:
            competitors = ", ".join(comp_shop.competitor_products) or "competitor products"

            summary = (
                f"Strategic Opportunities framework is ready for "
                f"{comp_shop.firman_product} against {competitors}. "
                f"Atlas will identify positioning opportunities, messaging gaps, "
                f"product advantages, and customer-facing recommendations."
            )
        else:
            summary = (
                "Strategic Opportunities framework is ready. "
                "Atlas will identify competitive openings, messaging opportunities, "
                "feature gaps, and business recommendations."
            )

        return TaskResult(
            task="Strategic Opportunities",
            summary=summary,
            confidence="Medium"
        )
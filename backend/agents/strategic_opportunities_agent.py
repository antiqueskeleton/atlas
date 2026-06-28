from backend.investigations.task_result import TaskResult


class StrategicOpportunitiesAgent:

    def run(self, analysis, request=None, provider_manager=None):
        if analysis is None:
            return TaskResult(
                task="Strategic Opportunities",
                summary="No active dataset is available to identify strategic opportunities.",
                confidence="Low"
            )

        summary = analysis["summary"]
        comp_shop = request.comp_shop if request else None

        if comp_shop:
            competitors = ", ".join(comp_shop.competitor_products) or "competitor products"

            result = (
                f"Strategic Opportunities analyzed {summary.evidence_count} responses for "
                f"{comp_shop.firman_product} against {competitors}. "
                f"Atlas found {summary.finding_counts_by_type.get('brand', 0)} brand signals "
                f"and {summary.finding_counts_by_type.get('feature', 0)} feature signals. "
                f"This supports identification of positioning opportunities, messaging gaps, "
                f"product advantages, and customer-facing recommendations."
            )
        else:
            result = (
                f"Strategic Opportunities analyzed {summary.evidence_count} responses. "
                f"Atlas found {summary.finding_counts_by_type.get('brand', 0)} brand signals "
                f"and {summary.finding_counts_by_type.get('feature', 0)} feature signals. "
                f"This supports identification of competitive openings, messaging opportunities, "
                f"feature gaps, and business recommendations."
            )

        return TaskResult(
            task="Strategic Opportunities",
            summary=result,
            confidence="Medium"
        )
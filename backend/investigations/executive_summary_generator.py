class ExecutiveSummaryGenerator:
    def generate(self, request, analysis):
        if analysis is None:
            return "No active dataset is available. Import or analyze a dataset first."

        summary = analysis["summary"]
        insights = analysis["insights"]

        insight_text = " ".join(
            insight.description for insight in insights
        )

        target = request.target_brand or "the selected brand"

        if request.intent == "explain":
            feature_context = (
                f" The question appears focused on {request.target_feature}."
                if request.target_feature
                else ""
            )

            return (
                f"Atlas reviewed {summary.evidence_count} responses. "
                f"{target} was evaluated against the current dataset.{feature_context} "
                f"{insight_text} "
                f"The main opportunity is to improve the connection between {target} "
                f"and the features AI systems already associate with stronger competitors."
            )

        if request.intent == "compare":
            competitor = request.competitor or "competitors"
            return (
                f"Atlas compared {target} against {competitor}. "
                f"The dataset contains {summary.evidence_count} responses. "
                f"{insight_text}"
            )

        return (
            f"Atlas analyzed {summary.evidence_count} responses. "
            f"{insight_text}"
        )
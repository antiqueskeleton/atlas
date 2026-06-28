from backend.investigations.executive_consensus import ExecutiveConsensus


class ExecutiveConsensusEngine:

    def generate(self, task_results):
        if not task_results:
            return ExecutiveConsensus(
                overall_read="No agent findings are available for consensus."
            )

        completed = [
            result for result in task_results
            if result.confidence != "Pending"
        ]

        if not completed:
            return ExecutiveConsensus(
                overall_read="No completed agent findings are available for consensus."
            )

        high_confidence = [
            result for result in completed
            if result.confidence == "High"
        ]

        overall_read = (
            f"Atlas reviewed {len(completed)} completed agent findings. "
            f"{len(high_confidence)} were high confidence. "
            "The combined findings should be reviewed as a directional executive read "
            "supported by the current dataset."
        )

        areas_of_agreement = [
            f"{result.task}: {result.summary[:220]}..."
            for result in completed
        ]

        key_risks = [
            "Some findings may overlap because multiple agents are analyzing the same evidence pool.",
            "Confidence should improve as Atlas receives more source data and stronger evidence ranking.",
        ]

        recommended_actions = [
            "Use these findings to identify the strongest competitive themes.",
            "Validate agent findings against customer data, product specifications, and market evidence.",
        ]

        return ExecutiveConsensus(
            overall_read=overall_read,
            areas_of_agreement=areas_of_agreement,
            key_risks=key_risks,
            recommended_actions=recommended_actions,
        )
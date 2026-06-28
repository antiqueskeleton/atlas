class ExecutiveConsensusEngine:

    def generate(self, task_results):
        if not task_results:
            return "No agent findings are available for consensus."

        completed = [
            result for result in task_results
            if result.confidence != "Pending"
        ]

        if not completed:
            return "No completed agent findings are available for consensus."

        high_confidence = [
            result for result in completed
            if result.confidence == "High"
        ]

        consensus = "Executive Consensus\n\n"

        consensus += "Overall Read:\n"
        consensus += (
            f"Atlas reviewed {len(completed)} completed agent findings. "
            f"{len(high_confidence)} were high confidence. "
            "The combined findings should be reviewed as a directional executive read "
            "supported by the current dataset.\n\n"
        )

        consensus += "Areas of Agreement:\n"
        for result in completed:
            consensus += f"• {result.task}: {result.summary[:220]}...\n"

        consensus += "\nKey Risks:\n"
        consensus += (
            "• Some findings may overlap because multiple agents are analyzing the same evidence pool.\n"
            "• Confidence should improve as Atlas receives more source data and stronger evidence ranking.\n"
        )

        consensus += "\nRecommended Executive Action:\n"
        consensus += (
            "Use these findings to identify the strongest competitive themes, "
            "then validate them against customer data, product specifications, and market evidence."
        )

        return consensus.strip()
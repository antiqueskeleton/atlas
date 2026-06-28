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

        medium_confidence = [
            result for result in completed
            if result.confidence == "Medium"
        ]

        consensus = "Executive Consensus:\n\n"

        consensus += f"Completed agent findings: {len(completed)}\n"
        consensus += f"High confidence findings: {len(high_confidence)}\n"
        consensus += f"Medium confidence findings: {len(medium_confidence)}\n\n"

        consensus += "Key Agent Conclusions:\n\n"

        for result in completed:
            consensus += (
                f"- {result.task} "
                f"({result.confidence}): "
                f"{result.summary[:240]}...\n"
            )

        return consensus.strip()
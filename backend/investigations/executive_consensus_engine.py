from backend.investigations.executive_consensus import ExecutiveConsensus
from backend.investigations.executive_prompt_builder import ExecutivePromptBuilder


class ExecutiveConsensusEngine:

    def generate(self, task_results, provider_manager=None):
        if not task_results:
            return ExecutiveConsensus(
                overall_read="No agent findings are available for consensus."
            )

        completed = [r for r in task_results if r.confidence != "Pending"]

        if not completed:
            return ExecutiveConsensus(
                overall_read="No completed agent findings are available for consensus."
            )

        areas_of_agreement = [
            f"{r.task}: {r.summary[:220]}…" for r in completed
        ]

        # Attempt LLM synthesis — falls back to rule-based if unavailable
        if provider_manager:
            try:
                prompt = ExecutivePromptBuilder().build(task_results)
                provider = provider_manager.get_active_provider()
                reasoning = provider.ask(prompt=prompt, context=None)
                return ExecutiveConsensus(
                    overall_read=reasoning.executive_summary or "",
                    confidence_score=min(100, len(completed) * 25),
                    areas_of_agreement=areas_of_agreement,
                    key_risks=reasoning.risks or [],
                    recommended_actions=reasoning.opportunities or [],
                )
            except Exception:
                pass  # fall through to rule-based

        # Rule-based fallback
        high_confidence = [r for r in completed if r.confidence == "High"]
        overall_read = (
            f"Atlas reviewed {len(completed)} completed agent findings. "
            f"{len(high_confidence)} were high confidence. "
            "The combined findings should be reviewed as a directional executive read "
            "supported by the current dataset."
        )
        key_risks = [
            "Some findings may overlap because multiple agents are analyzing the same evidence pool.",
            "Confidence should improve as Atlas receives more source data and stronger evidence ranking.",
        ]
        recommended_actions = [
            "Use these findings to identify the strongest competitive themes.",
            "Validate agent findings against customer data, product specifications, and market evidence.",
        ]
        confidence_score = min(100, (len(high_confidence) * 25) + (len(completed) * 10))

        return ExecutiveConsensus(
            overall_read=overall_read,
            confidence_score=confidence_score,
            areas_of_agreement=areas_of_agreement,
            key_risks=key_risks,
            recommended_actions=recommended_actions,
        )

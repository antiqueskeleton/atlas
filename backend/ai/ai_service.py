from backend.ai.prompt_builder import PromptBuilder
from backend.ai.provider_manager import ProviderManager
from backend.models.ai_reasoning import AIReasoning


class AIService:
    def __init__(self, provider_manager: ProviderManager):
        self.provider_manager = provider_manager
        self.prompt_builder = PromptBuilder()
        self.last_prompt = None

    def reason(self, request, analysis):
        provider = self.provider_manager.get_active_provider()

        if analysis is None:
            self.last_prompt = None

            return AIReasoning(
                executive_summary="No active dataset is available. Import or analyze a dataset before running an investigation.",
                confidence="Low",
                risks=[
                    "Atlas cannot generate evidence-based reasoning without an active dataset."
                ],
                follow_up_questions=[
                    "Would you like to import a response dataset?"
                ],
                provider=provider.provider_name,
            )

        from backend.investigations.evidence_ranker import EvidenceRanker

        ranked_evidence = EvidenceRanker().rank(
            request,
            analysis,
            limit=8
        )

        prompt = self.prompt_builder.build(
            request,
            analysis,
            ranked_evidence=ranked_evidence
        )

        self.last_prompt = prompt

        return provider.ask(
            prompt=prompt,
            context=None
        )
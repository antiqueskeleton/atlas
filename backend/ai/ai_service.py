from backend.ai.prompt_builder import PromptBuilder
from backend.ai.provider_manager import ProviderManager


class AIService:

    def __init__(self, provider_manager: ProviderManager):
        self.provider_manager = provider_manager
        self.prompt_builder = PromptBuilder()

    def reason(self, request, analysis):
        prompt = self.prompt_builder.build(
            request,
            analysis
        )

        provider = self.provider_manager.get_active_provider()

        reasoning = provider.ask(
            prompt=prompt,
            context=None
        )

        return reasoning
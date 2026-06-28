from backend.agents.agent_prompt_builder import AgentPromptBuilder


class AgentAIService:

    def __init__(self, provider_manager):
        self.provider_manager = provider_manager
        self.prompt_builder = AgentPromptBuilder()

    def ask(self, task_name, request, analysis):
        prompt = self.prompt_builder.build(
            task_name,
            request,
            analysis
        )

        provider = self.provider_manager.get_active_provider()

        reasoning = provider.ask(
            prompt=prompt,
            context=None
        )

        return reasoning
from backend.visibility.prompt_library import PromptLibrary
from backend.visibility.visibility_repository import VisibilityRepository
from backend.visibility.visibility_runner import VisibilityRunner
from backend.visibility.visibility_analytics import VisibilityAnalytics


class VisibilityService:
    def __init__(self, provider_manager):
        self.provider_manager = provider_manager
        self.prompt_library = PromptLibrary()
        self.runner = VisibilityRunner(provider_manager)
        self.analytics = VisibilityAnalytics()
        self.repository = VisibilityRepository()

    def run(self, prompt_set="default", provider_name=None):
        prompts = self.prompt_library.get(prompt_set)

        result = self.runner.run_prompt_set(
            prompts=prompts,
            provider_name=provider_name,
            prompt_set=prompt_set,
        )

        self.repository.save_run(result["run"])
        self.repository.save_responses(result["responses"])

        return result

    def list_runs(self):
        return self.repository.list_runs()
    
    def analytics_summary(self):
        responses = self.repository.list_responses()
        return self.analytics.summarize_responses(responses)
    
    def get_responses_for_run(self, run_id):
        return self.repository.get_responses_for_run(run_id)
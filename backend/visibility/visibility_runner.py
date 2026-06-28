from datetime import datetime
from uuid import uuid4

from backend.models.visibility_run import VisibilityRun
from backend.models.visibility_response import VisibilityResponse


class VisibilityRunner:

    def __init__(self, provider_manager):
        self.provider_manager = provider_manager

    def run_prompt_set(self, prompts, provider_name=None, prompt_set="Default"):
        provider_name = provider_name or self.provider_manager.active_provider_name
        self.provider_manager.set_active_provider(provider_name)

        provider = self.provider_manager.get_active_provider()

        run = VisibilityRun(
            run_id=str(uuid4()),
            provider=provider.provider_name,
            model=getattr(provider, "model", "unknown"),
            prompt_set=prompt_set,
            started_at=datetime.now(),
        )

        responses = []

        for prompt in prompts:
            reasoning = provider.ask(prompt)

            responses.append(
                VisibilityResponse(
                    run_id=run.run_id,
                    provider=provider.provider_name,
                    model=run.model,
                    prompt=prompt,
                    response=reasoning.executive_summary,
                    collected_at=datetime.now(),
                )
            )

        run.completed_at = datetime.now()
        run.status = "Completed"
        run.response_count = len(responses)
        run.duration_seconds = (
            run.completed_at - run.started_at
        ).total_seconds()

        return {
            "run": run,
            "responses": responses,
        }
from datetime import datetime
from typing import Callable
from uuid import uuid4

from backend.models.visibility_run import VisibilityRun
from backend.models.visibility_response import VisibilityResponse


class VisibilityRunner:

    def __init__(self, provider_manager):
        self.provider_manager = provider_manager

    def run_prompt_set(
        self,
        prompts: list[str],
        provider_name: str | None = None,
        prompt_set: str = "Default",
        progress_callback: Callable[[int, int], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
        paused: Callable[[], bool] | None = None,
    ) -> dict:
        """
        Run every prompt against one provider and return a run + responses dict.

        Args:
            prompts: list of prompt strings to send
            provider_name: provider key; falls back to active provider
            prompt_set: label stored with the run record
            progress_callback: called after each prompt with (completed, total)
            cancelled: called before each prompt; if True, stops the run early

        Returns:
            {"run": VisibilityRun, "responses": list[VisibilityResponse]}
        """
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

        for i, prompt in enumerate(prompts):
            # Block here while paused, unblocks on resume or cancel
            if paused:
                import time
                while paused():
                    time.sleep(0.05)

            if cancelled and cancelled():
                break

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

            if progress_callback:
                progress_callback(i + 1, len(prompts))

        run.completed_at = datetime.now()
        run.status = "completed" if not (cancelled and cancelled()) else "cancelled"
        run.response_count = len(responses)
        run.duration_seconds = (run.completed_at - run.started_at).total_seconds()

        return {"run": run, "responses": responses}

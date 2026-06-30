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
        provider=None,
        prompt_set: str = "Default",
        prompt_families: dict[str, str] | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
        paused: Callable[[], bool] | None = None,
    ) -> dict:
        if provider is None:
            provider_name = provider_name or self.provider_manager.active_provider_name
            provider = self.provider_manager.get_provider(provider_name)

        run = VisibilityRun(
            run_id=str(uuid4()),
            provider=provider.provider_name,
            model=getattr(provider, "model", "unknown"),
            prompt_set=prompt_set,
            started_at=datetime.now(),
        )

        responses = []
        error_count = 0

        for i, prompt in enumerate(prompts):
            if paused:
                import time
                while paused():
                    time.sleep(0.05)

            if cancelled and cancelled():
                break

            reasoning = provider.ask(prompt)

            if reasoning.is_error:
                error_count += 1
            else:
                family = (prompt_families or {}).get(prompt, "")
                responses.append(
                    VisibilityResponse(
                        run_id=run.run_id,
                        provider=provider.provider_name,
                        model=run.model,
                        prompt=prompt,
                        response=reasoning.executive_summary,
                        collected_at=datetime.now(),
                        family_name=family,
                    )
                )

            if progress_callback:
                progress_callback(i + 1, len(prompts))

        run.completed_at = datetime.now()
        run.status = "completed" if not (cancelled and cancelled()) else "cancelled"
        run.response_count = len(responses)
        run.error_count = error_count
        run.duration_seconds = (run.completed_at - run.started_at).total_seconds()

        return {"run": run, "responses": responses}

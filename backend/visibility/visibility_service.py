from typing import Callable

from backend.visibility.prompt_library import PromptLibrary
from backend.visibility.visibility_repository import VisibilityRepository
from backend.visibility.visibility_runner import VisibilityRunner
from backend.visibility.visibility_analytics import VisibilityAnalytics


class VisibilityService:
    def __init__(self, provider_manager, target_brand=""):
        self.provider_manager = provider_manager
        self.target_brand = target_brand
        self.prompt_library = PromptLibrary()
        self.runner = VisibilityRunner(provider_manager)
        self.analytics = VisibilityAnalytics(target_brand=target_brand)
        self.repository = VisibilityRepository()
        # One-time backfill for responses collected before the cue-zone
        # cache existed (#81) — idempotent and cheap (a single COUNT query)
        # once nothing is left to backfill, so safe to call on every
        # construction rather than needing a separate "have we done this
        # already" flag.
        self.repository.backfill_cue_zone_cache()
        self._analytics_cache: dict | None = None
        self._analytics_cache_count: int = -1
        self._analytics_cache_target_brand: str | None = None

    def run(
        self,
        prompt_set: str = "default",
        provider_name: str | None = None,
        provider=None,
        progress_callback: Callable[[int, int], None] | None = None,
        cancelled: Callable[[], bool] | None = None,
        paused: Callable[[], bool] | None = None,
        prompts: list[str] | None = None,
        prompt_families: dict[str, str] | None = None,
        logger=None,
    ) -> dict:
        if prompts is None:
            prompts = self.prompt_library.get(prompt_set)
        result = self.runner.run_prompt_set(
            prompts=prompts,
            provider_name=provider_name,
            provider=provider,
            prompt_set=prompt_set,
            prompt_families=prompt_families,
            progress_callback=progress_callback,
            cancelled=cancelled,
            paused=paused,
            logger=logger,
        )
        self.repository.save_run(result["run"])
        self.repository.save_responses(result["responses"])
        self._analytics_cache = None  # invalidate on new data
        return result

    def list_runs(self):
        return self.repository.list_runs()

    def analytics_summary(self):
        # #35: reload brand/feature/channel terms every call — cheap relative
        # to summarize_responses(), and the response-count-keyed cache below
        # can't tell on its own whether the term SET changed (e.g. a brand
        # added mid-session with no new responses collected), so force a
        # recompute whenever reload_terms() reports a real change.
        if self.analytics.reload_terms():
            self._analytics_cache = None
        # #80: also invalidate on a target_brand change alone (same response
        # count, same term set) — without this, re-syncing target_brand in
        # refresh() has no visible effect until the response count next
        # changes, since target_visibility_score is keyed off target_brand
        # but the cache wasn't tracking it.
        if self.analytics.target_brand != self._analytics_cache_target_brand:
            self._analytics_cache = None
        count = self.repository.count_responses()
        if self._analytics_cache is not None and count == self._analytics_cache_count:
            return self._analytics_cache
        responses = self.repository.list_responses()  # all rows, no limit
        result = self.analytics.summarize_responses(responses)
        self._analytics_cache = result
        self._analytics_cache_count = count
        self._analytics_cache_target_brand = self.analytics.target_brand
        return result

    def get_responses_for_run(self, run_id):
        return self.repository.get_responses_for_run(run_id)

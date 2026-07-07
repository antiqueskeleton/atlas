from collections import defaultdict

from backend.visibility.brand_matcher import resolve_target_brand
from backend.visibility.visibility_analytics import VisibilityAnalytics
from backend.visibility.visibility_repository import VisibilityRepository

# #59: thresholds for flagging a meaningful visibility drop. Deliberately a
# simple, tunable fixed-point threshold rather than anything statistical —
# "cheap first version" per the original backlog note. Compared per-PROVIDER
# (not pooled across all providers) since different providers have very
# different baseline visibility levels on their own — pooling would make a
# provider mix shift look like a real drop.
_DROP_THRESHOLD_POINTS = 15.0
_MIN_PRIOR_RUNS = 3
_BASELINE_WINDOW = 5


def sync_model_change_events(visibility_repository, knowledge_repository) -> int:
    """
    #90: a provider silently swapping models (its own default rotation, or
    a manual change in Settings) shifts visibility scores with zero market
    change behind it. Detect every model transition in the stored run
    history and log it into the existing #67 event system, dated at the
    transition, so every Trends chart gets a dotted marker where the
    measuring instrument changed. Idempotent — already-logged transitions
    (matched on description + date) are skipped. Returns how many new
    events were logged.
    """
    runs = visibility_repository.list_runs() or []
    # rows: (run_id, provider, model, prompt_set, started_at, ...) newest
    # first — walk oldest→newest per provider to see transitions in order.
    by_provider: dict[str, list] = {}
    for row in sorted(runs, key=lambda r: r[4] or ""):
        provider, model, started_at = row[1], row[2], row[4]
        if provider and model:
            by_provider.setdefault(provider, []).append((model, started_at))

    try:
        existing = {
            (description, (occurred_at or "")[:10])
            for event_type, description, occurred_at
            in knowledge_repository.list_events()
            if event_type == "model_change"
        }
    except Exception:
        existing = set()

    logged = 0
    for provider, sequence in by_provider.items():
        previous_model = None
        for model, started_at in sequence:
            if previous_model is not None and model != previous_model:
                description = f"{provider} model changed: {previous_model} → {model}"
                key = (description, (started_at or "")[:10])
                if key not in existing:
                    knowledge_repository.log_event(
                        "model_change", description, occurred_at=started_at)
                    existing.add(key)
                    logged += 1
            previous_model = model
    return logged


class TrendsService:
    """Aggregates per-run visibility data into time-series structures for charting."""

    def __init__(self, target_brand=""):
        self.target_brand = target_brand
        self.repository = VisibilityRepository()
        # One-time backfill for responses collected before the cue-zone
        # cache existed (#81) — idempotent/cheap once nothing is left to
        # backfill; not relying on VisibilityService having already run
        # this, since page construction order isn't guaranteed.
        self.repository.backfill_cue_zone_cache()
        self.analytics = VisibilityAnalytics(target_brand=target_brand)
        # #90: keep model-change markers in sync with run history — cheap
        # (one pass over the runs list) and idempotent, and a failure here
        # must never block the Trends page from loading.
        try:
            from backend.knowledge.knowledge_repository import KnowledgeRepository
            sync_model_change_events(self.repository, KnowledgeRepository())
        except Exception:
            pass

    def _resolved_target(self) -> str:
        """
        self.target_brand is whatever casing the user typed into Settings —
        resolve it to the canonical casing used as dict/list keys throughout
        this file (self.analytics.brands), same fix as VisibilityAnalytics.
        summarize_responses(). Without this, "FIRMAN" or "firman" wouldn't
        match the "Firman" entries already in `selected`/`ranked` below, so
        the "always include target brand" logic would append a second,
        all-zero, wrong-cased ghost entry instead of finding the real one.
        """
        return resolve_target_brand(self.target_brand, self.analytics.brands)

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_run_summaries(self) -> list[dict]:
        """
        Returns one dict per completed run, in chronological order.
        Each dict has:
            datetime, date, provider, prompt_set, response_count,
            target_score, brand_rates, feature_rates,
            brand_position_shares, first_mention_share
        """
        # #35: reload once before the loop below, not once per run inside it —
        # summarize_responses() runs once per historical run here, so reloading
        # inside it would redundantly re-query Knowledge/CSVs for every run.
        self.analytics.reload_terms()

        runs = self.repository.list_runs()
        summaries = []

        for run in runs:
            run_id, provider, model, prompt_set, started_at, completed_at, status, response_count, duration, *_ = run

            if status != "completed":
                continue

            responses = self.repository.get_responses_for_run(run_id)
            if not responses:
                continue

            # Extend with prompt_set at index 7 for VisibilityAnalytics
            extended = [r + (prompt_set,) for r in responses]
            summary = self.analytics.summarize_responses(extended)

            total = summary["total_responses"] or 1
            brand_rates = {
                brand: round(count / total * 100, 1)
                for brand, count in summary["brand_counts"].items()
            }
            feature_rates = {
                feat: round(count / total * 100, 1)
                for feat, count in summary["feature_counts"].items()
            }

            summaries.append({
                "run_id": run_id,
                "datetime": started_at,
                "date": started_at[:10],
                "label": started_at[5:16].replace("T", " "),  # MM-DD HH:MM
                "provider": provider,
                "prompt_set": prompt_set,
                "response_count": total,
                "target_score": summary["target_visibility_score"],
                "brand_rates": brand_rates,
                "feature_rates": feature_rates,
                "brand_position_shares": summary["brand_position_share"],
                "first_mention_share": summary.get("first_mention_share", {}),
            })

        summaries.reverse()  # chronological order
        return summaries

    def brand_time_series(self, summaries: list[dict], top_n: int = 6) -> dict:
        """
        Returns {brand: [rate_per_run, ...]} for the top_n most-mentioned brands.
        Target brand is always included even if outside top_n.
        """
        totals: dict[str, float] = defaultdict(float)
        for s in summaries:
            for brand, rate in s["brand_rates"].items():
                totals[brand] += rate

        ranked = sorted(totals, key=lambda b: -totals[b])
        selected = ranked[:top_n]
        target = self._resolved_target()
        if target and target not in selected:
            selected.append(target)

        return {
            brand: [s["brand_rates"].get(brand, 0) for s in summaries]
            for brand in selected
        }

    def feature_time_series(self, summaries: list[dict], top_n: int = 6) -> dict:
        """Returns {feature: [rate_per_run, ...]} for the top_n features."""
        totals: dict[str, float] = defaultdict(float)
        for s in summaries:
            for feat, rate in s["feature_rates"].items():
                totals[feat] += rate

        ranked = sorted(totals, key=lambda f: -totals[f])[:top_n]
        return {
            feat: [s["feature_rates"].get(feat, 0) for s in summaries]
            for feat in ranked
        }

    def provider_averages(self, summaries: list[dict]) -> dict:
        """Returns {provider: avg_target_score} across all runs."""
        totals: dict[str, list] = defaultdict(list)
        for s in summaries:
            totals[s["provider"]].append(s["target_score"])
        return {
            p: round(sum(scores) / len(scores), 1)
            for p, scores in totals.items()
        }

    def prompt_set_averages(self, summaries: list[dict]) -> dict:
        """Returns {prompt_set: avg_target_score}."""
        totals: dict[str, list] = defaultdict(list)
        for s in summaries:
            totals[s["prompt_set"]].append(s["target_score"])
        return {
            ps: round(sum(scores) / len(scores), 1)
            for ps, scores in totals.items()
        }

    def best_prompt_set_for_target(self, summaries: list[dict]) -> str:
        """Returns the prompt set name with the highest avg target brand score."""
        ps_avgs = self.prompt_set_averages(summaries)
        if not ps_avgs:
            return "—"
        return max(ps_avgs, key=ps_avgs.get)

    def brand_snapshot(self, summaries: list[dict], top_n: int = 8) -> dict[str, float]:
        """Returns {brand: avg_mention_rate} across all runs, top_n + target brand."""
        totals: dict[str, float] = defaultdict(float)
        counts: dict[str, int] = defaultdict(int)
        for s in summaries:
            for brand, rate in s["brand_rates"].items():
                totals[brand] += rate
                counts[brand] += 1
        avgs = {b: round(totals[b] / counts[b], 1) for b in totals}
        ranked = sorted(avgs, key=lambda b: -avgs[b])[:top_n]
        target = self._resolved_target()
        if target and target not in ranked:
            ranked.append(target)
        return {b: avgs.get(b, 0.0) for b in ranked}

    def detect_visibility_drops(self, summaries: list[dict]) -> list[dict]:
        """
        Flags providers whose MOST RECENT run's target_score dropped
        meaningfully below their own trailing baseline (last _BASELINE_WINDOW
        runs before that one, or however many are available). Requires at
        least _MIN_PRIOR_RUNS prior runs for that provider before flagging
        anything — too little history makes any "drop" just noise, not a
        real signal.

        Returns a list of dicts (most severe drop first), each:
            provider, latest_score, baseline_score, drop, latest_date
        """
        by_provider: dict[str, list[dict]] = defaultdict(list)
        for s in summaries:  # summaries are already chronological
            by_provider[s["provider"]].append(s)

        drops = []
        for provider, runs in by_provider.items():
            if len(runs) < _MIN_PRIOR_RUNS + 1:
                continue
            latest = runs[-1]
            prior = runs[:-1][-_BASELINE_WINDOW:]
            baseline = sum(r["target_score"] for r in prior) / len(prior)
            drop = baseline - latest["target_score"]
            if baseline > 0 and drop >= _DROP_THRESHOLD_POINTS:
                drops.append({
                    "provider": provider,
                    "latest_score": latest["target_score"],
                    "baseline_score": round(baseline, 1),
                    "drop": round(drop, 1),
                    "latest_date": latest["date"],
                })

        return sorted(drops, key=lambda d: -d["drop"])

    def position_time_series(self, summaries: list[dict], top_n: int = 5) -> dict:
        """
        Returns {brand: [position1_share_per_run, ...]} for position 1 (first mention).
        """
        totals: dict[str, float] = defaultdict(float)
        for s in summaries:
            for brand, share in s["first_mention_share"].items():
                totals[brand] += share

        ranked = sorted(totals, key=lambda b: -totals[b])[:top_n]
        target = self._resolved_target()
        if target and target not in ranked:
            ranked.append(target)

        return {
            brand: [s["first_mention_share"].get(brand, 0) for s in summaries]
            for brand in ranked
        }

from collections import defaultdict

from backend.visibility.visibility_analytics import VisibilityAnalytics
from backend.visibility.visibility_repository import VisibilityRepository


class TrendsService:
    """Aggregates per-run visibility data into time-series structures for charting."""

    def __init__(self, target_brand=""):
        self.target_brand = target_brand
        self.repository = VisibilityRepository()
        self.analytics = VisibilityAnalytics(target_brand=target_brand)

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_run_summaries(self) -> list[dict]:
        """
        Returns one dict per completed run, in chronological order.
        Each dict has:
            datetime, date, provider, prompt_set, response_count,
            target_score, brand_rates, feature_rates,
            brand_position_shares, first_mention_share
        """
        runs = self.repository.list_runs()
        summaries = []

        for run in runs:
            run_id, provider, model, prompt_set, started_at, completed_at, status, response_count, duration = run

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
        if self.target_brand and self.target_brand not in selected:
            selected.append(self.target_brand)

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

    def position_time_series(self, summaries: list[dict], top_n: int = 5) -> dict:
        """
        Returns {brand: [position1_share_per_run, ...]} for position 1 (first mention).
        """
        totals: dict[str, float] = defaultdict(float)
        for s in summaries:
            for brand, share in s["first_mention_share"].items():
                totals[brand] += share

        ranked = sorted(totals, key=lambda b: -totals[b])[:top_n]
        if self.target_brand and self.target_brand not in ranked:
            ranked.append(self.target_brand)

        return {
            brand: [s["first_mention_share"].get(brand, 0) for s in summaries]
            for brand in ranked
        }

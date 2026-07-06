"""
Targeted Review orchestration (#25): collect real platform-presence numbers
per brand, persist snapshots, and turn the latest snapshots into findings
in the feature's defining pattern — Gap → Why It Matters for AI Visibility
→ Specific Tactics to Close It.

The WHY/TACTICS text is deliberately rule-based per platform+metric, not
LLM-generated: the whole point of this page is grounding Atlas's
AI-inferred channel gaps in verifiable numbers, so the explanation layer
must be deterministic and auditable, never hallucinatable. Tactic wording
follows the platform-specific guidance already scoped in the project plan
(Amazon Vine / Request-a-Review; YouTube creator seeding + comparison
content; Reddit organic participation).
"""
from backend.targeted_review.editorial_search_provider import (
    EDITORIAL_SITES,
    EditorialSearchProvider,
)
from backend.targeted_review.reddit_provider import RedditPlatformProvider
from backend.targeted_review.retailer_provider import RetailerListingProvider
from backend.targeted_review.targeted_review_repository import TargetedReviewRepository
from backend.targeted_review.youtube_provider import YouTubePlatformProvider
from backend.visibility.brand_matcher import resolve_target_brand

PLATFORMS = {
    "youtube": YouTubePlatformProvider,
    "reddit": RedditPlatformProvider,
    "editorial": EditorialSearchProvider,
    "retail": RetailerListingProvider,
}

# Count-style gaps only fire when the leader has a real lead, not noise —
# 1.5× matches the "meaningful difference" bar used informally elsewhere
# (e.g. channel-gap lead factors) and avoids flagging 12-vs-10 as a gap.
_GAP_RATIO = 1.5
# Star ratings compare on absolute closeness instead: a 4.5 vs 4.4 spread is
# parity; 0.2 stars is where retail conversion studies (and shoppers) start
# noticing. Below 4.0 flat is flagged regardless of competitors.
_RATING_GAP = 0.2
_RATING_FLOOR = 4.0


class TargetedReviewService:
    def __init__(self, config_service, target_brand: str = "", repository=None):
        self.config_service = config_service
        self.target_brand = target_brand
        self.repository = repository or TargetedReviewRepository()

    # ── Providers ─────────────────────────────────────────────────────────────

    def get_provider(self, platform_key: str):
        provider = PLATFORMS[platform_key]()
        provider.set_credentials({
            field: self.config_service.get_platform_credential(platform_key, field)
            for field in provider.credential_fields
        })
        return provider

    def platform_ready(self, platform_key: str) -> tuple[bool, str]:
        """(ready, reason-if-not) — lets the UI grey out a Collect button
        with an explanation instead of failing on click."""
        provider = self.get_provider(platform_key)
        missing = provider.missing_credentials()
        if missing:
            return False, f"Missing in Settings: {', '.join(missing)}"
        if platform_key == "retail" and not self.repository.list_product_urls():
            return False, "No product URLs saved yet — add listings below."
        return True, ""

    # ── Collection ────────────────────────────────────────────────────────────

    def collect_platform(self, platform_key: str, brands: list[str],
                         progress_cb=None) -> list[dict]:
        """
        Fetch fresh presence data and persist one snapshot per brand.
        progress_cb(done, total, label) is called before each fetch so a UI
        worker can show live progress. Per-brand failures stay in-band in
        each finding's "error" — one failed brand never aborts the rest.
        """
        provider = self.get_provider(platform_key)

        if platform_key == "retail":
            findings = self._collect_retail(provider, brands, progress_cb)
        else:
            findings = []
            for i, brand in enumerate(brands):
                if progress_cb:
                    progress_cb(i, len(brands), brand)
                findings.append(provider.fetch_brand_presence(brand))

        self.repository.save_findings(provider.platform_name, findings)
        return findings

    def _collect_retail(self, provider, brands: list[str], progress_cb) -> list[dict]:
        """One aggregated finding per brand from its saved listing URLs."""
        by_brand: dict[str, list[str]] = {}
        for _id, brand, url, _added in self.repository.list_product_urls():
            if not brands or brand in brands:
                by_brand.setdefault(brand, []).append(url)

        findings = []
        total = sum(len(urls) for urls in by_brand.values())
        done = 0
        for brand, urls in by_brand.items():
            listings = []
            for url in urls:
                if progress_cb:
                    progress_cb(done, total, f"{brand} — {url[:60]}")
                listings.append(provider.fetch_listing(url))
                done += 1
            findings.append(_aggregate_retail(provider.platform_name, brand, listings))
        return findings

    # ── Gap analysis ──────────────────────────────────────────────────────────

    def gap_analysis(self, platform_key: str) -> list[dict]:
        """
        Compare the target brand against competitors on the latest stored
        snapshots. Returns finding dicts:
            {type: "gap"|"strength", platform, metric_label,
             target_brand, target_display, leader_brand, leader_display,
             why, tactics: [str, ...]}
        ordered gaps first (biggest lead factor first), strengths after.
        """
        platform_name = PLATFORMS[platform_key].platform_name
        latest = self.repository.latest_findings(platform_name)
        usable = {b: m for b, m in latest.items() if not m.get("error")}
        if not usable:
            return []

        target = resolve_target_brand(self.target_brand, usable.keys())
        if target not in usable:
            return []

        findings = []
        for metric in _PLATFORM_METRICS.get(platform_key, []):
            finding = self._compare_metric(platform_key, platform_name,
                                           metric, target, usable)
            if finding:
                findings.append(finding)

        findings.sort(key=lambda f: (f["type"] != "gap", -f.get("ratio", 0)))
        return findings

    def _compare_metric(self, platform_key: str, platform_name: str,
                        metric: dict, target: str, usable: dict) -> dict | None:
        value_of = metric["value"]
        target_value = value_of(usable[target])
        competitors = [(b, value_of(m)) for b, m in usable.items() if b != target]
        competitors = [(b, v) for b, v in competitors if v is not None]
        if target_value is None or not competitors:
            return None

        leader_brand, leader_value = max(competitors, key=lambda bv: bv[1])
        base = {
            "platform": platform_name,
            "metric_label": metric["label"],
            "target_brand": target,
            "target_display": metric["fmt"](target_value),
            "leader_brand": leader_brand,
            "leader_display": metric["fmt"](leader_value),
        }

        if metric.get("is_rating"):
            # Absolute-closeness comparison (see _RATING_GAP/_RATING_FLOOR).
            if target_value < leader_value - _RATING_GAP or target_value < _RATING_FLOOR:
                return {**base, "type": "gap", "ratio": leader_value - target_value,
                        "why": metric["why"](target, leader_brand),
                        "tactics": metric["tactics"](target, leader_brand, usable)}
            return {**base, "type": "strength", "ratio": 0,
                    "why": f"{target}'s average rating holds its own against "
                           f"{leader_brand} — protect it.", "tactics": []}

        if leader_value > target_value and \
                (target_value == 0 or leader_value / max(target_value, 1) >= _GAP_RATIO):
            ratio = round(leader_value / max(target_value, 1), 1)
            return {**base, "type": "gap", "ratio": ratio,
                    "why": metric["why"](target, leader_brand),
                    "tactics": metric["tactics"](target, leader_brand, usable)}
        if target_value >= leader_value and target_value > 0:
            return {**base, "type": "strength", "ratio": 0,
                    "why": f"{target} leads every tracked competitor on this "
                           f"metric — keep feeding it.", "tactics": []}
        return None  # behind, but within noise — not worth an action card


# ── Retail aggregation ────────────────────────────────────────────────────────

def _aggregate_retail(platform_name: str, brand: str, listings: list[dict]) -> dict:
    ok = [l for l in listings if not l.get("error")]
    review_counts = [l["review_count"] for l in ok if l.get("review_count")]
    # Rating averaged weighted by each listing's review count — a 4.8 with 12
    # reviews shouldn't offset a 3.9 with 4,000.
    rated = [(l["rating"], l.get("review_count") or 1) for l in ok if l.get("rating")]
    avg_rating = (
        round(sum(r * w for r, w in rated) / sum(w for _, w in rated), 2)
        if rated else None
    )
    return {
        "brand": brand,
        "platform": platform_name,
        "listings": listings,
        "listings_ok": len(ok),
        "listings_failed": len(listings) - len(ok),
        "total_reviews": sum(review_counts) if review_counts else None,
        "avg_rating": avg_rating,
        "error": "" if ok else "No listing could be read for this brand.",
    }


# ── Metric definitions ────────────────────────────────────────────────────────

def _top_subreddits_of(usable: dict, brand: str) -> str:
    subs = [s for s, _ in (usable.get(brand, {}).get("top_subreddits") or [])[:3]]
    return ", ".join(f"r/{s}" for s in subs) if subs else "r/Generators, r/preppers"


_PLATFORM_METRICS: dict[str, list[dict]] = {
    "youtube": [
        {
            "label": "YouTube videos (estimated search results)",
            "value": lambda m: m.get("video_results"),
            "fmt": lambda v: f"~{v:,} videos",
            "why": lambda t, l: (
                f"YouTube reviews are among the sources AI assistants cite most in "
                f"generator recommendations, and the sheer volume of public video "
                f"content shapes which brands AI models learn to treat as major. "
                f"{l}'s larger video footprint means more review data, more "
                f"comparisons, and more transcripts feeding AI training and search."
            ),
            "tactics": lambda t, l, u: [
                "Seed 2-3 YouTube reviewers in the 50K-500K subscriber range with review units",
                f"Publish comparison content targeting \"{l} vs {t}\" search queries",
                "Create setup/tutorial videos targeting feature keywords "
                "(quiet operation, dual fuel, remote start, home backup)",
            ],
        },
        {
            "label": "New videos in the last 12 months",
            "value": lambda m: m.get("recent_videos_365d"),
            "fmt": lambda v: f"~{v:,} videos",
            "why": lambda t, l: (
                f"Fresh content matters separately from back-catalog volume: AI "
                f"answers favor current-model information, and a year of {l} "
                f"uploads outpacing {t} means AI increasingly describes the "
                f"category in {l}'s terms."
            ),
            "tactics": lambda t, l, u: [
                "Ship review units for every new model launch, not just flagships",
                "Refresh top-performing older videos with current-year updates via creators",
                "Time creator content to storm-season demand spikes (June + December)",
            ],
        },
        {
            "label": "Views across each brand's top-10 videos",
            "value": lambda m: m.get("top_videos_total_views"),
            "fmt": lambda v: f"{v:,} views",
            "why": lambda t, l: (
                f"View concentration shows whose content consumers actually watch. "
                f"High-view {l} videos generate the comment threads, transcripts, "
                f"and follow-up content that AI models absorb as consumer consensus."
            ),
            "tactics": lambda t, l, u: [
                "Prioritize the 2-3 highest-subscriber generator channels for seeding",
                f"Sponsor a head-to-head test against {l}'s best-selling model",
                "Add chapter markers/transcripts to owned videos so AI can parse them",
            ],
        },
    ],
    "reddit": [
        {
            "label": "Reddit posts mentioning the brand (last year)",
            "value": lambda m: m.get("posts_last_year"),
            "fmt": lambda v: f"{v:,}+ posts" if v >= 100 else f"{v:,} posts",
            "why": lambda t, l: (
                f"AI assistants treat Reddit threads as 'real owner' evidence and "
                f"cite them directly in shopping answers. {l} dominating the "
                f"conversation volume means owner anecdotes, praise, and "
                f"troubleshooting habits get absorbed in {l}'s favor."
            ),
            "tactics": lambda t, l, u: [
                f"Build organic presence in {_top_subreddits_of(u, l)} — answer "
                f"questions as a knowledgeable participant, never as an ad",
                "Monitor brand mentions weekly; respond to unanswered owner questions",
                "Run an expert AMA in r/Generators timed to hurricane season",
            ],
        },
        {
            "label": "Reddit engagement (upvotes + comments, last year)",
            "value": lambda m: (
                None if m.get("total_score") is None
                else (m.get("total_score") or 0) + (m.get("total_comments") or 0)
            ),
            "fmt": lambda v: f"{v:,} interactions",
            "why": lambda t, l: (
                f"Engagement measures which threads the community actually "
                f"amplifies — highly-upvoted {l} threads are exactly the ones AI "
                f"summarizes when asked what owners recommend."
            ),
            "tactics": lambda t, l, u: [
                "Contribute detailed, photo-backed answers in high-traffic threads "
                "(long posts earn upvotes; drive-by brand mentions get buried)",
                "Share genuinely useful content — sizing guides, wattage charts — "
                "that threads link back to",
            ],
        },
    ],
    "editorial": [
        {
            "label": "Editorial sites covering the brand",
            "value": lambda m: m.get("sites_with_coverage"),
            "fmt": lambda v: f"{v} of {len(EDITORIAL_SITES)} sites",
            "why": lambda t, l: (
                f"AI assistants lean on a small set of authority review sites — "
                f"Consumer Reports, Wirecutter, CNET — as ground truth for 'best "
                f"generator' answers. When {l} appears in those roundups and {t} "
                f"doesn't, AI answers inherit that shortlist verbatim: absence "
                f"from the sites IS absence from the answer."
            ),
            "tactics": lambda t, l, u: [
                "Pitch products into annual roundup updates ('best generators "
                "2026') at CNET, Popular Mechanics, and Bob Vila — editors "
                "refresh these yearly and need units to test",
                "Send review units + full spec press kits to editorial testers "
                "at every model launch",
                "Run an affiliate program so editorial sites earn commission on "
                "links — Wirecutter-style sites preferentially cover brands "
                "they can monetize",
            ],
        },
        {
            "label": "Editorial articles mentioning the brand (estimated)",
            "value": lambda m: m.get("total_results"),
            "fmt": lambda v: f"~{v:,} articles",
            "why": lambda t, l: (
                f"Depth of coverage compounds: every additional {l} article is "
                f"another citation, snippet, and training-data passage that AI "
                f"models absorb — repeated appearances read as market leadership."
            ),
            "tactics": lambda t, l, u: [
                "Offer expert commentary for storm-season preparedness stories "
                "(reporters need quotable sources every hurricane season)",
                "Send product-launch press releases to trade press and the home/"
                "garden desks of major outlets",
                "Publish original data (e.g. outage statistics, sizing surveys) "
                "editorial sites will cite and link",
            ],
        },
    ],
    "retail": [
        {
            "label": "Total retailer reviews (saved listings)",
            "value": lambda m: m.get("total_reviews"),
            "fmt": lambda v: f"{v:,} reviews",
            "why": lambda t, l: (
                f"Review counts on retailer listings are among the strongest trust "
                f"signals AI shopping answers repeat ('highly rated with thousands "
                f"of reviews'). {l}'s review depth becomes a self-reinforcing "
                f"recommendation loop that {t} is outside of."
            ),
            "tactics": lambda t, l, u: [
                "Enroll eligible products in Amazon Vine",
                "Automate Seller Central 'Request a Review' for every Amazon order",
                "Add post-purchase review prompts (QR insert card) across all channels",
                "Syndicate reviews across Home Depot / Lowe's / Walmart listings",
            ],
        },
        {
            "label": "Average star rating (review-weighted)",
            "value": lambda m: m.get("avg_rating"),
            "fmt": lambda v: f"{v:.2f} stars",
            "is_rating": True,
            "why": lambda t, l: (
                f"Average ratings get quoted verbatim in AI comparisons — a listing "
                f"under {_RATING_FLOOR:.1f} stars, or visibly behind {l}, becomes a "
                f"'reviewers note reliability concerns' line in AI answers."
            ),
            "tactics": lambda t, l, u: [
                "Prioritize service recovery on any listing under 4.0 stars",
                "Respond publicly to critical reviews with concrete fixes",
                "Audit lowest-rated SKUs for recurring defect themes and fix upstream",
            ],
        },
    ],
}

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
import re

from backend.targeted_review.ai_overview_provider import AIOverviewProvider
from backend.targeted_review.bestbuy_provider import BestBuyProvider
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
    "aioverview": AIOverviewProvider,
    "bestbuy": BestBuyProvider,
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
    def __init__(self, config_service=None, target_brand: str = "", repository=None):
        # config_service is only needed for COLLECTION (credential lookup in
        # get_provider/platform_ready) — read-only consumers like
        # build_presence_block() construct this with config_service=None to
        # run gap_analysis() over already-stored snapshots.
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

        if platform_key == "youtube":
            # Official channel URLs from the discovered social links — the
            # cheap, rich half of the YouTube picture (~3 units per brand).
            provider.channel_urls = {
                b: (self.repository.get_social_links(b) or {}).get("youtube", "")
                for b in brands
            }

        if platform_key == "retail":
            findings = self._collect_retail(provider, brands, progress_cb)
        elif platform_key == "aioverview":
            # Collection-level platform: 5 shared Google searches serve
            # every brand at once (#97) — never one sweep per brand.
            findings = provider.fetch_all(brands, progress_cb=progress_cb)
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

    # ── Tracked creators (influencers) ────────────────────────────────────────
    # A different shape from brand tracking: one specific named channel/user
    # followed over time, not a target-vs-competitor comparison — no gap
    # analysis applies here, just cadence and engagement. Flat list, not
    # nested under a brand, since one creator may cover several.

    def list_tracked_creators(self) -> list[tuple]:
        """[(id, platform, handle, display_name, notes, added_at)]."""
        return self.repository.list_creators()

    @staticmethod
    def normalize_creator_handle(platform: str, handle: str) -> str:
        """
        Accept what people actually type, store what the fetchers need.
        Real v1.0 test failure (item 6.7): the user entered
        "@MikesWeatherPage" — a bare handle, not a URL — and YouTube
        resolution failed. YouTube: bare @handle, plain name, UC… channel
        id, or full URL all normalize to a youtube.com URL form.
        Reddit: strip "u/" / "@" / a pasted profile URL down to the bare
        username the /user/{name} endpoints take.
        """
        handle = (handle or "").strip()
        if not handle:
            return handle
        if platform == "youtube":
            if "youtube.com" in handle.lower():
                return handle
            if handle.startswith("UC") and len(handle) >= 12 and " " not in handle:
                return f"https://www.youtube.com/channel/{handle}"
            return f"https://www.youtube.com/@{handle.lstrip('@')}"
        if platform == "reddit":
            match = re.search(r"reddit\.com/(?:user|u)/([\w\-]+)", handle,
                              re.IGNORECASE)
            if match:
                return match.group(1)
            return handle.lstrip("@").removeprefix("u/").removeprefix("U/")
        return handle

    def add_creator(self, platform: str, handle: str, display_name: str,
                    notes: str = "") -> bool:
        handle = self.normalize_creator_handle(platform, handle)
        return self.repository.add_creator(platform, handle, display_name, notes)

    def remove_creator(self, creator_id: int):
        self.repository.remove_creator(creator_id)

    def collect_creator_performance(self, progress_cb=None) -> list[dict]:
        """
        Refresh every tracked creator across both platforms in one pass —
        each check costs only a handful of quota units (versus ~400 for a
        brand search), so unlike brand collection, granular per-platform
        control isn't needed here. Findings are saved under distinct
        platform-name keys ("YouTube Creators"/"Reddit Creators") in the
        same generic findings table brand collection uses, keyed by the
        creator's display name in the existing "brand" column.
        """
        creators = self.repository.list_creators()
        if not creators:
            return []

        yt_provider = self.get_provider("youtube")
        reddit_provider = self.get_provider("reddit")

        yt_findings: list[dict] = []
        reddit_findings: list[dict] = []
        total = len(creators)
        for i, (_id, platform, handle, display_name, _notes, _added) in enumerate(creators):
            if progress_cb:
                progress_cb(i, total, display_name)
            # Normalized at add time too, but re-normalized here so creators
            # saved before the normalizer existed (bare "@handle" rows)
            # still resolve without the user re-adding them.
            handle = self.normalize_creator_handle(platform, handle)
            if platform == "youtube":
                api_key = yt_provider.credentials.get("api_key", "")
                result = yt_provider.fetch_creator_performance(api_key, handle)
                result["brand"] = display_name
                yt_findings.append(result)
            elif platform == "reddit":
                client_id = reddit_provider.credentials.get("client_id", "")
                client_secret = reddit_provider.credentials.get("client_secret", "")
                result = reddit_provider.fetch_creator_performance(
                    client_id, client_secret, handle)
                result["brand"] = display_name
                reddit_findings.append(result)

        if yt_findings:
            self.repository.save_findings("YouTube Creators", yt_findings)
        if reddit_findings:
            self.repository.save_findings("Reddit Creators", reddit_findings)
        return yt_findings + reddit_findings

    def latest_creator_findings(self) -> dict[str, dict]:
        """{display_name: metrics} across both platforms, each tagged with
        which platform it came from for the UI table."""
        combined: dict[str, dict] = {}
        for platform_name, key in (("YouTube Creators", "youtube"),
                                    ("Reddit Creators", "reddit")):
            for name, metrics in self.repository.latest_findings(platform_name).items():
                combined[name] = {**metrics, "platform": key}
        return combined

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

        # Full standings across every brand with a value on this metric, so a
        # card shows the real competitive landscape — the target's rank and
        # who's ahead — not just the #1 leader (R3). Higher is better for
        # every current metric (views, subscribers, videos, rating), so sort
        # descending; competition ranking (1,2,2,4) handles ties.
        fmt = metric["fmt"]
        ranked = sorted(
            ((b, value_of(m)) for b, m in usable.items() if value_of(m) is not None),
            key=lambda bv: bv[1], reverse=True,
        )
        leaderboard, prev_val, rank = [], None, 0
        for i, (b, v) in enumerate(ranked):
            if v != prev_val:
                rank, prev_val = i + 1, v
            leaderboard.append({"rank": rank, "brand": b,
                                "display": fmt(v), "is_target": b == target})
        target_rank = next(e["rank"] for e in leaderboard if e["is_target"])

        base = {
            "platform": platform_name,
            "metric_label": metric["label"],
            "target_brand": target,
            "target_display": metric["fmt"](target_value),
            "leader_brand": leader_brand,
            "leader_display": metric["fmt"](leader_value),
            "target_rank": target_rank,
            "field_size": len(leaderboard),
            "leaderboard": leaderboard,
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


# ── Intelligence Engine integration ──────────────────────────────────────────

def build_presence_block(repository, target_brand: str) -> str:
    """
    Plain-text summary of the latest measured platform presence, injected
    into the Intelligence Engine's opportunity/briefing prompts (#25's
    design intent: findings feed the Intelligence Engine as ground truth,
    not a separate silo).

    Includes the deterministic MEASURED GAP lines from gap_analysis() so the
    LLM receives pre-validated comparisons rather than re-deriving (and
    possibly mis-deriving) them from the raw numbers. Returns an explicit
    "no data" sentence when nothing has been collected — the prompts tell
    the model never to invent platform numbers, so the empty state must be
    unambiguous, not just an absent section.
    """
    sections = []
    for key, provider_cls in PLATFORMS.items():
        latest = repository.latest_findings(provider_cls.platform_name)
        usable = {b: m for b, m in latest.items() if not m.get("error")}
        if not usable:
            continue

        newest = max(m.get("collected_at", "")[:10] for m in usable.values())
        lines = [f"{provider_cls.platform_name} (collected {newest}):"]
        for brand, metrics in usable.items():
            lines.append(f"  {brand}: {_summarize_brand_metrics(key, metrics)}")

        gap_service = TargetedReviewService(None, target_brand, repository=repository)
        for g in gap_service.gap_analysis(key):
            if g["type"] == "gap":
                rank = (f" ({g['target_brand']} ranks #{g['target_rank']} of "
                        f"{g['field_size']})" if g.get("target_rank") else "")
                lines.append(
                    f"  MEASURED GAP — {g['metric_label']}: "
                    f"{g['target_brand']} {g['target_display']} vs "
                    f"{g['leader_brand']} {g['leader_display']}{rank}"
                )
        sections.append("\n".join(lines))

    if not sections:
        return ("No measured platform data collected yet — the Targeted Review "
                "page has not been run. Do not invent platform numbers.")
    return "\n\n".join(sections)


def _summarize_brand_metrics(platform_key: str, m: dict) -> str:
    if platform_key == "youtube":
        text = (f"{m.get('relevant_results_top100') or 0:,} relevant videos in the "
                f"top-100 search results, {m.get('recent_relevant_365d') or 0:,} "
                f"fresh in last 12 months; {m.get('top_videos_total_views') or 0:,} "
                f"views across the top-10 relevant videos all-time vs "
                f"{m.get('top_videos_recent_total_views') or 0:,} across the top-10 "
                f"published in the last 12 months (current-period attention, where "
                f"a newer brand can lead despite a smaller back-catalog)")
        if m.get("channel_subscribers") is not None:
            text += (f", official channel: {m['channel_subscribers']:,} subscribers, "
                     f"{m.get('channel_uploads_365d') or 0} uploads in last year")
        voice = m.get("owner_voice") or {}
        if voice.get("comments_sampled"):
            text += (f"; owner voice ({voice['comments_sampled']} top comments "
                     f"sampled): {voice.get('mentioning_brand', 0)} mention the "
                     f"brand, {voice.get('recommendation_cues', 0)} with "
                     f"recommendation cues, {voice.get('negative_cues', 0)} with "
                     f"negative cues")
        return text
    if platform_key == "reddit":
        capped = "+" if m.get("posts_capped") else ""
        engagement = (m.get("total_score") or 0) + (m.get("total_comments") or 0)
        subs = ", ".join(f"r/{s}" for s, _ in (m.get("top_subreddits") or [])[:3])
        return (f"{m.get('posts_last_year') or 0}{capped} posts in last year, "
                f"{engagement:,} combined upvotes+comments"
                + (f", most active in {subs}" if subs else ""))
    if platform_key == "editorial":
        strongest = m.get("strongest_site")
        return (f"covered by {m.get('sites_with_coverage') or 0} of "
                f"{m.get('sites_checked') or 0} tracked authority review sites, "
                f"~{m.get('total_results') or 0:,} articles"
                + (f", strongest: {strongest}" if strongest else ""))
    if platform_key == "aioverview":
        return (f"named in {m.get('appearances') or 0} of "
                f"{m.get('queries_checked') or 0} Google AI Overview buying "
                f"queries ({m.get('overviews_present') or 0} queries showed an "
                f"AI Overview)")
    if platform_key == "bestbuy":
        parts = [f"{m.get('listings_found') or 0} Best Buy listings"]
        if m.get("total_reviews"):
            parts.append(f"{m['total_reviews']:,} customer reviews")
        if m.get("avg_rating") is not None:
            parts.append(f"{m['avg_rating']:.2f} avg stars")
        return ", ".join(parts)
    if platform_key == "retail":
        reviews = m.get("total_reviews")
        parts = [f"{reviews:,} retailer reviews" if reviews is not None
                 else "review count unavailable"]
        if m.get("avg_rating") is not None:
            parts.append(f"{m['avg_rating']:.2f} avg stars")
        parts.append(f"across {m.get('listings_ok') or 0} saved listings")
        return ", ".join(parts)
    return ""


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
            "label": "Relevant videos in the top-100 search results",
            "value": lambda m: m.get("relevant_results_top100"),
            "fmt": lambda v: f"{v:,} of top-100",
            "why": lambda t, l: (
                f"YouTube reviews are among the sources AI assistants cite most in "
                f"generator recommendations, and the share of search results a "
                f"brand actually owns shapes which brands AI models learn to treat "
                f"as major. {l} filling more of the results page means more review "
                f"data, more comparisons, and more transcripts feeding AI answers."
            ),
            "tactics": lambda t, l, u: [
                "Seed 2-3 YouTube reviewers in the 50K-500K subscriber range with review units",
                f"Publish comparison content targeting \"{l} vs {t}\" search queries",
                "Create setup/tutorial videos targeting feature keywords "
                "(quiet operation, dual fuel, remote start, home backup)",
            ],
        },
        {
            "label": "Fresh videos in the last 12 months (top-100 sample)",
            "value": lambda m: m.get("recent_relevant_365d"),
            "fmt": lambda v: f"{v:,} of top-100",
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
            "label": "Official YouTube channel subscribers",
            "value": lambda m: m.get("channel_subscribers"),
            "fmt": lambda v: f"{v:,} subscribers",
            "why": lambda t, l: (
                f"An official channel is the one YouTube surface a brand fully "
                f"controls. {l}'s larger subscriber base means every upload gets "
                f"guaranteed reach, comments, and watch time — the engagement "
                f"signals that push its content into search results and AI answers."
            ),
            "tactics": lambda t, l, u: [
                "Publish setup/troubleshooting series — utility content earns "
                "subscribers between purchases",
                "Cross-promote the channel on packaging, manuals, and "
                "post-purchase emails (QR code to a first-start walkthrough)",
                f"Study {l}'s top-performing upload formats and counter-program",
            ],
        },
        {
            "label": "Views across each brand's top-10 relevant videos",
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
        {
            "label": "Views on videos published in the last 12 months (top-100 sample)",
            "value": lambda m: m.get("top_videos_recent_total_views"),
            "fmt": lambda v: f"{v:,} recent views",
            "why": lambda t, l: (
                f"Recent view volume is the one YouTube dimension a newer brand "
                f"can win outright: all-time totals are dominated by years-old "
                f"uploads, but attention on this year's videos reflects the CURRENT "
                f"market. {l} leading here means AI answers are being shaped by "
                f"fresh consumer watch behavior, not just legacy content — and it "
                f"is where {t} can outperform on momentum even while trailing on "
                f"back-catalog volume."
            ),
            "tactics": lambda t, l, u: [
                "Concentrate seeding on a few high-subscriber creators for "
                "launch-window view spikes rather than spreading budget thin",
                f"Commission a current-year head-to-head review against {l}'s newest model",
                "Time new-model content to storm-season demand (June + December) "
                "when generator searches and watch time peak",
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
    "aioverview": [
        {
            "label": "Appearances in Google AI Overviews (5 buying queries)",
            "value": lambda m: m.get("appearances"),
            "fmt": lambda v: f"{v} of 5 queries",
            "why": lambda t, l: (
                f"Google's AI Overview is the highest-reach AI answer surface "
                f"there is — it sits above every organic result for the exact "
                f"queries generator buyers ask. {l} being named in these "
                f"overviews while {t} is absent means Google's AI is actively "
                f"steering buyers elsewhere at the top of the funnel."
            ),
            "tactics": lambda t, l, u: [
                "Win the sources the Overview cites: editorial roundups and "
                "high-authority comparison pages (see Editorial tab gaps)",
                "Publish structured, spec-rich comparison content targeting the "
                "exact overview queries (best portable generator, quietest "
                "inverter generator)",
                "Build out product schema markup sitewide — Overviews lean on "
                "structured data",
            ],
        },
    ],
    "bestbuy": [
        {
            "label": "Best Buy customer reviews",
            "value": lambda m: m.get("total_reviews"),
            "fmt": lambda v: f"{v:,} reviews",
            "why": lambda t, l: (
                f"Best Buy is a top-3 US electronics retailer and its review "
                f"corpus feeds AI shopping answers. {l}'s deeper review base "
                f"there reads as mainstream credibility that {t} lacks on the "
                f"same shelf."
            ),
            "tactics": lambda t, l, u: [
                "Get core SKUs stocked/listed on BestBuy.com (marketplace or "
                "direct) — presence precedes reviews",
                "Sync post-purchase review prompts for Best Buy orders",
                "Match the listing depth (photos, specs, Q&A) of the category leader",
            ],
        },
        {
            "label": "Best Buy average rating (review-weighted)",
            "value": lambda m: m.get("avg_rating"),
            "fmt": lambda v: f"{v:.2f} stars",
            "is_rating": True,
            "why": lambda t, l: (
                f"Ratings on a mainstream shelf like Best Buy get quoted in AI "
                f"comparisons verbatim — under {_RATING_FLOOR:.1f} stars, or "
                f"visibly behind {l}, becomes a repeated caution line."
            ),
            "tactics": lambda t, l, u: [
                "Service-recover every sub-4-star Best Buy review thread",
                "Audit lowest-rated SKUs for recurring defect themes",
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

"""
YouTube presence via the official Data API v3 (#25, build-sequence step 1 —
free tier, no approval gate).

Uses plain HTTPS against googleapis.com with an API key rather than the
google-api-python-client SDK — a handful of GET requests need no client
library, and it keeps the dependency list unchanged.

REWORKED after real-data validation (2026-07-06) exposed two problems with
the first version's estimate-based metrics:
  1. search.list's pageInfo.totalResults is an APPROXIMATION with a hard
     1,000,000 cap — real collection showed CAT and Champion both pinned at
     exactly 1,000,000 and Firman at an absurd ~338k, making brand-vs-brand
     comparison meaningless. totalResults is no longer used for anything.
  2. Ambiguous brand names poison results: '"CAT" generator' returned
     actual cat-the-animal videos ("cat generator", "Gatorrada (Cat-Toast)")
     with millions of views, inflating every CAT metric.

Now every metric is COUNTED from actually-returned results and filtered
for relevance: a video only counts if its title mentions the brand (word-
boundary match) AND contains a generator-market term (generator/watt/
inverter/...). Counts are over the top-100 search results per query — an
honest, comparable sample, displayed as such — never an extrapolated total.
Known residual limitation: a title like "cat generator" (a literal cat
video) passes any text filter; sampling 100 titles keeps such strays to
noise level, but ambiguous brands still carry more of it.

Quota reality (default free tier = 10,000 units/day): each search page
costs 100 units; 2 pages × 2 queries + one videos.list ≈ 401 units per
brand, so a 6-brand collection ≈ 2,400 — several full runs per day free.
"""
import re
from datetime import datetime, timedelta, timezone

import requests

from backend.targeted_review.base_platform_provider import PlatformProvider

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
_PLAYLIST_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
_TIMEOUT = 20
_PAGES = 2          # 2 pages × 50 = top-100 sample per query
_PAGE_SIZE = 50

# A sampled title must contain one of these to count as generator-market
# content — kills music videos, AI "video generator" tools, and (most)
# cat-the-animal content that brand terms alone let through.
_MARKET_TERMS = re.compile(
    r"generator|watt|inverter|portable power|standby|dual.?fuel|tri.?fuel|kva|\bkw\b",
    re.IGNORECASE,
)


def _api_error_message(response) -> str:
    """Extract Google's human-readable error from a non-200 response body."""
    try:
        return response.json()["error"]["message"]
    except Exception:
        return f"HTTP {response.status_code}"


def _brand_pattern(brand: str) -> re.Pattern:
    """Word-boundary matcher so 'CAT' doesn't match 'category' — multi-word
    brands ('Briggs & Stratton') match on the full phrase."""
    return re.compile(r"\b" + re.escape(brand.strip()) + r"\b", re.IGNORECASE)


class YouTubePlatformProvider(PlatformProvider):
    platform_name = "YouTube"
    credential_fields = {"api_key": "API Key"}

    def __init__(self):
        super().__init__()
        # brand -> official channel URL, injected by the service from the
        # discovered social links. Channel metrics cost ~3 quota units per
        # brand (channels.list + playlistItems) versus ~400 for the search
        # sampling — by far the cheapest signal this provider collects.
        self.channel_urls: dict[str, str] = {}

    def fetch_brand_presence(self, brand: str) -> dict:
        base = {"brand": brand, "platform": self.platform_name}
        api_key = self.credentials.get("api_key", "")
        if not api_key:
            return {**base, "error": "No YouTube API key configured — add one in Settings."}

        query = f'"{brand}" portable generator'
        year_ago = (datetime.now(timezone.utc) - timedelta(days=365)) \
            .strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            all_items, err = self._paged_search(api_key, query)
            if err:
                return {**base, "error": err}
            recent_items, err = self._paged_search(api_key, query, published_after=year_ago)
            if err:
                return {**base, "error": err}

            relevant = _filter_relevant(all_items, brand)
            recent_relevant = _filter_relevant(recent_items, brand)

            stats_by_id: dict[str, dict] = {}
            video_ids = [v["video_id"] for v in relevant][:50]
            if video_ids:
                stats = requests.get(_VIDEOS_URL, params={
                    "part": "statistics", "id": ",".join(video_ids), "key": api_key,
                }, timeout=_TIMEOUT)
                if stats.status_code == 200:
                    stats_by_id = {
                        item["id"]: item.get("statistics", {})
                        for item in stats.json().get("items", [])
                    }
        except requests.RequestException as exc:
            return {**base, "error": f"YouTube request failed: {exc}"}

        for video in relevant:
            video_stats = stats_by_id.get(video["video_id"], {})
            try:
                video["views"] = int(video_stats.get("viewCount", 0))
            except (TypeError, ValueError):
                video["views"] = 0
            try:
                video["comments"] = int(video_stats.get("commentCount", 0))
            except (TypeError, ValueError):
                video["comments"] = 0
        relevant.sort(key=lambda v: -v["views"])

        channel = self._channel_metrics(api_key, self.channel_urls.get(brand, ""))

        return {
            **base,
            "sample_size": len(all_items),
            "relevant_results_top100": len(relevant),
            "recent_relevant_365d": len(recent_relevant),
            "top_videos": relevant[:10],
            "top_videos_total_views": sum(v["views"] for v in relevant[:10]),
            **channel,
            "error": "",
        }

    def _channel_metrics(self, api_key: str, channel_url: str) -> dict:
        """Official-channel statistics for a brand with a discovered channel
        URL. All failures degrade to empty fields — channel data is an
        enrichment and must never fail a brand whose search sampling worked."""
        empty = {"channel_url": channel_url or "", "channel_subscribers": None,
                 "channel_total_views": None, "channel_video_count": None,
                 "channel_uploads_365d": None, "channel_latest_upload": ""}
        params = _channel_lookup_params(channel_url)
        if not params:
            return empty
        try:
            resp = requests.get(_CHANNELS_URL, params={
                "part": "statistics,contentDetails", "key": api_key, **params,
            }, timeout=_TIMEOUT)
            items = resp.json().get("items", []) if resp.status_code == 200 else []
            if not items:
                return empty
            stats = items[0].get("statistics", {})
            uploads_id = (items[0].get("contentDetails", {})
                          .get("relatedPlaylists", {}).get("uploads", ""))

            uploads_365d, latest = None, ""
            if uploads_id:
                pl = requests.get(_PLAYLIST_URL, params={
                    "part": "contentDetails", "playlistId": uploads_id,
                    "maxResults": 50, "key": api_key,
                }, timeout=_TIMEOUT)
                if pl.status_code == 200:
                    dates = sorted((item.get("contentDetails", {})
                                    .get("videoPublishedAt", "") or "")[:10]
                                   for item in pl.json().get("items", []))
                    dates = [d for d in dates if d]
                    if dates:
                        latest = dates[-1]
                        year_ago = (datetime.now(timezone.utc)
                                    - timedelta(days=365)).strftime("%Y-%m-%d")
                        uploads_365d = sum(1 for d in dates if d >= year_ago)

            def _int(value):
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None

            return {
                "channel_url": channel_url,
                "channel_subscribers": _int(stats.get("subscriberCount")),
                "channel_total_views": _int(stats.get("viewCount")),
                "channel_video_count": _int(stats.get("videoCount")),
                "channel_uploads_365d": uploads_365d,
                "channel_latest_upload": latest,
            }
        except requests.RequestException:
            return empty

    def _paged_search(self, api_key: str, query: str,
                      published_after: str = "") -> tuple[list[dict], str]:
        """Up to _PAGES × _PAGE_SIZE real results (not estimates).
        Returns (items, error) — in-band error string, empty on success."""
        items: list[dict] = []
        page_token = ""
        for _ in range(_PAGES):
            params = {
                "part": "snippet", "q": query, "type": "video",
                "maxResults": _PAGE_SIZE, "regionCode": "US",
                "relevanceLanguage": "en", "key": api_key,
            }
            if published_after:
                params["publishedAfter"] = published_after
            if page_token:
                params["pageToken"] = page_token
            resp = requests.get(_SEARCH_URL, params=params, timeout=_TIMEOUT)
            if resp.status_code != 200:
                return [], f"YouTube search failed: {_api_error_message(resp)}"
            data = resp.json()
            for item in data.get("items", []):
                video_id = item.get("id", {}).get("videoId", "")
                snippet = item.get("snippet", {})
                if video_id:
                    items.append({
                        "video_id": video_id,
                        "title": snippet.get("title", ""),
                        "channel": snippet.get("channelTitle", ""),
                        "published": snippet.get("publishedAt", "")[:10],
                        "views": 0,
                    })
            page_token = data.get("nextPageToken", "")
            if not page_token:
                break
        return items, ""


def _filter_relevant(items: list[dict], brand: str) -> list[dict]:
    """Title must mention the brand (word boundary) AND a generator-market
    term — pure and separately testable, since this filter is the whole
    difference between real brand presence and cat videos."""
    brand_re = _brand_pattern(brand)
    seen: set[str] = set()
    relevant = []
    for item in items:
        title = item.get("title", "")
        if item["video_id"] in seen:
            continue
        if brand_re.search(title) and _MARKET_TERMS.search(title):
            seen.add(item["video_id"])
            relevant.append(dict(item))
    return relevant


def _channel_lookup_params(channel_url: str) -> dict | None:
    """Map a channel URL form to channels.list lookup params. /c/NAME custom
    URLs have no direct API lookup and return None (skipped, not errored)."""
    if not channel_url:
        return None
    match = re.search(r"youtube\.com/channel/(UC[\w-]+)", channel_url, re.IGNORECASE)
    if match:
        return {"id": match.group(1)}
    match = re.search(r"youtube\.com/@([\w.\-]+)", channel_url, re.IGNORECASE)
    if match:
        return {"forHandle": match.group(1)}
    match = re.search(r"youtube\.com/user/([\w.\-]+)", channel_url, re.IGNORECASE)
    if match:
        return {"forUsername": match.group(1)}
    return None

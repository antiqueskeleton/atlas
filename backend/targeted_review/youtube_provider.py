"""
YouTube presence via the official Data API v3 (#25, build-sequence step 1 —
free tier, no approval gate).

Uses plain HTTPS against googleapis.com with an API key rather than the
google-api-python-client SDK — three GET requests need no client library,
and it keeps the dependency list unchanged.

Quota reality (default free tier = 10,000 units/day): each search.list call
costs 100 units and videos.list costs 1, so one brand costs ~201 units and
a 7-brand collection run ~1,400 — dozens of full runs per day before the
quota matters.

Known data caveat, surfaced in the UI rather than hidden: search.list's
pageInfo.totalResults is YouTube's own ESTIMATE of matching videos, not an
exact count. It's directionally reliable for brand-vs-brand comparison
(the only use here), not an auditable absolute number.
"""
from datetime import datetime, timedelta, timezone

import requests

from backend.targeted_review.base_platform_provider import PlatformProvider

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
_TIMEOUT = 20


def _api_error_message(response) -> str:
    """Extract Google's human-readable error from a non-200 response body."""
    try:
        return response.json()["error"]["message"]
    except Exception:
        return f"HTTP {response.status_code}"


class YouTubePlatformProvider(PlatformProvider):
    platform_name = "YouTube"
    credential_fields = {"api_key": "API Key"}

    def fetch_brand_presence(self, brand: str) -> dict:
        base = {"brand": brand, "platform": self.platform_name}
        api_key = self.credentials.get("api_key", "")
        if not api_key:
            return {**base, "error": "No YouTube API key configured — add one in Settings."}

        query = f'"{brand}" generator'
        try:
            # ── 1. All-time search: estimated volume + top-10 by relevance ──
            all_time = requests.get(_SEARCH_URL, params={
                "part": "snippet", "q": query, "type": "video",
                "maxResults": 10, "regionCode": "US",
                "relevanceLanguage": "en", "key": api_key,
            }, timeout=_TIMEOUT)
            if all_time.status_code != 200:
                return {**base, "error": f"YouTube search failed: {_api_error_message(all_time)}"}
            all_time_data = all_time.json()

            # ── 2. Trailing-year search: is anyone making FRESH content? ────
            year_ago = (datetime.now(timezone.utc) - timedelta(days=365)) \
                .strftime("%Y-%m-%dT%H:%M:%SZ")
            recent = requests.get(_SEARCH_URL, params={
                "part": "snippet", "q": query, "type": "video",
                "maxResults": 1, "publishedAfter": year_ago,
                "regionCode": "US", "relevanceLanguage": "en", "key": api_key,
            }, timeout=_TIMEOUT)
            recent_total = (
                recent.json().get("pageInfo", {}).get("totalResults", 0)
                if recent.status_code == 200 else 0
            )

            # ── 3. Statistics for the top videos found in step 1 ────────────
            video_ids = [
                item["id"]["videoId"]
                for item in all_time_data.get("items", [])
                if item.get("id", {}).get("videoId")
            ]
            stats_by_id: dict[str, dict] = {}
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

        return {**base, **parse_youtube_results(all_time_data, recent_total, stats_by_id),
                "error": ""}


def parse_youtube_results(search_data: dict, recent_total: int,
                          stats_by_id: dict[str, dict]) -> dict:
    """
    Pure transform of raw API payloads into the stored metric shape —
    separated from the network calls so tests exercise the real parsing
    against canned payloads without any HTTP.
    """
    top_videos = []
    for item in search_data.get("items", []):
        video_id = item.get("id", {}).get("videoId", "")
        snippet = item.get("snippet", {})
        views = 0
        try:
            views = int(stats_by_id.get(video_id, {}).get("viewCount", 0))
        except (TypeError, ValueError):
            pass
        top_videos.append({
            "title": snippet.get("title", ""),
            "channel": snippet.get("channelTitle", ""),
            "published": snippet.get("publishedAt", "")[:10],
            "views": views,
            "video_id": video_id,
        })
    top_videos.sort(key=lambda v: -v["views"])

    return {
        "video_results": search_data.get("pageInfo", {}).get("totalResults", 0),
        "recent_videos_365d": recent_total,
        "top_videos": top_videos,
        "top_videos_total_views": sum(v["views"] for v in top_videos),
    }

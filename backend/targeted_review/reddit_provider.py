"""
Reddit presence via the official API (#25, build-sequence step 2 — free at
this scale, needs a one-time app registration at reddit.com/prefs/apps but
no approval gate).

Auth is application-only OAuth (client_credentials grant): no Reddit user
account password involved, just the app's client id + secret exchanged for
a bearer token per collection run. Reddit's API rules require a descriptive
User-Agent on every request — omitting it gets requests throttled or
blocked outright, so it's set explicitly on both the token exchange and the
search calls.

Search scope: site-wide `"{brand}" generator` over the trailing year,
sorted by top. Counting stops at Reddit's 100-results-per-request cap;
`posts_capped` tells the UI to display "100+" instead of implying an exact
total. Known limitation for ambiguous brand names (e.g. CAT): the quoted
brand + "generator" keyword scopes matches, but can't fully rule out
false positives — same caveat the rest of Atlas's substring brand matching
already documents.
"""
from collections import Counter
from datetime import datetime, timezone

import requests

from backend.targeted_review.base_platform_provider import PlatformProvider

_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
_SEARCH_URL = "https://oauth.reddit.com/search"
_USER_AGENT = "windows:atlas-ai-targeted-review:v0.9 (competitive research tool)"
_TIMEOUT = 20


class RedditPlatformProvider(PlatformProvider):
    platform_name = "Reddit"
    credential_fields = {
        "client_id": "App Client ID",
        "client_secret": "App Client Secret",
    }

    def __init__(self):
        super().__init__()
        # App-only tokens last ~1 hour — far longer than any collection run,
        # so one token exchange serves every brand in the run instead of
        # re-authenticating per brand.
        self._token = ""

    def _get_token(self, client_id: str, client_secret: str) -> tuple[str, str]:
        """Returns (token, error) — token cached for the provider's lifetime."""
        if self._token:
            return self._token, ""
        token_resp = requests.post(
            _TOKEN_URL,
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        )
        if token_resp.status_code != 200:
            return "", (f"Reddit auth failed (HTTP {token_resp.status_code}) "
                        "— check the client ID/secret in Settings.")
        token = token_resp.json().get("access_token", "")
        if not token:
            return "", ("Reddit auth returned no access token — "
                        "check the client ID/secret in Settings.")
        self._token = token
        return token, ""

    def fetch_brand_presence(self, brand: str) -> dict:
        base = {"brand": brand, "platform": self.platform_name}
        client_id = self.credentials.get("client_id", "")
        client_secret = self.credentials.get("client_secret", "")
        if not client_id or not client_secret:
            return {**base, "error": "Reddit app credentials not configured — "
                                     "add client ID + secret in Settings."}

        try:
            token, auth_error = self._get_token(client_id, client_secret)
            if auth_error:
                return {**base, "error": auth_error}

            search_resp = requests.get(
                _SEARCH_URL,
                params={
                    "q": f'"{brand}" generator', "limit": 100,
                    "sort": "top", "t": "year", "type": "link", "raw_json": 1,
                },
                headers={"Authorization": f"bearer {token}",
                         "User-Agent": _USER_AGENT},
                timeout=_TIMEOUT,
            )
            if search_resp.status_code != 200:
                return {**base, "error": f"Reddit search failed (HTTP {search_resp.status_code})."}
            search_data = search_resp.json()
        except requests.RequestException as exc:
            return {**base, "error": f"Reddit request failed: {exc}"}

        return {**base, **parse_reddit_results(search_data), "error": ""}


def parse_reddit_results(search_data: dict) -> dict:
    """
    Pure transform of a Reddit /search listing payload into the stored
    metric shape — separated from the network calls so tests exercise the
    real parsing against canned payloads without any HTTP.
    """
    children = search_data.get("data", {}).get("children", [])
    posts = [c.get("data", {}) for c in children if c.get("kind") == "t3"]

    subreddit_counts = Counter(p.get("subreddit", "") for p in posts if p.get("subreddit"))

    top_posts = []
    for p in sorted(posts, key=lambda p: -(p.get("score") or 0))[:5]:
        created = ""
        try:
            created = datetime.fromtimestamp(
                p.get("created_utc", 0), tz=timezone.utc
            ).strftime("%Y-%m-%d")
        except (TypeError, ValueError, OSError):
            pass
        top_posts.append({
            "title": p.get("title", ""),
            "subreddit": p.get("subreddit", ""),
            "score": p.get("score") or 0,
            "comments": p.get("num_comments") or 0,
            "created": created,
        })

    return {
        "posts_last_year": len(posts),
        "posts_capped": len(posts) >= 100,
        "total_score": sum(p.get("score") or 0 for p in posts),
        "total_comments": sum(p.get("num_comments") or 0 for p in posts),
        "top_subreddits": subreddit_counts.most_common(5),
        "top_posts": top_posts,
    }

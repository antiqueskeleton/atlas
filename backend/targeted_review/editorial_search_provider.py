"""
Editorial-site coverage via the Google Custom Search JSON API (#25,
build-sequence step 4 — one search integration covering every authority
review site, instead of a one-off scraper per site).

Measures, per brand, how much coverage exists on the editorial sites AI
assistants actually cite as authorities in generator recommendations
(Consumer Reports, Wirecutter, CNET, Popular Mechanics, Bob Vila, Forbes)
— one site-restricted query per (brand, site) using the `site:` operator,
which unlike the API's siteSearch parameter reliably supports the
path-scoped Wirecutter case (nytimes.com/wirecutter).

Cost reality (free tier = 100 queries/day, then $5/1,000): 6 sites per
brand → a 6-brand collection run costs 36 queries, so ~2 full runs/day
free. The API key can be the SAME Google Cloud key used for YouTube if the
Custom Search API is also enabled on that project; the engine ID (cx) comes
from creating a Programmable Search Engine set to "search the entire web".

Same estimate caveat as YouTube's totalResults: Google's result counts are
directionally reliable for brand-vs-brand comparison, not exact.
"""
import time

import requests

from backend.targeted_review.base_platform_provider import PlatformProvider

_SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
_TIMEOUT = 20

# (display label, site: operator target). Module constant for now — worth
# making user-editable in Knowledge once the working set stabilizes.
EDITORIAL_SITES = [
    ("Consumer Reports", "consumerreports.org"),
    ("Wirecutter (NYT)", "nytimes.com/wirecutter"),
    ("CNET", "cnet.com"),
    ("Popular Mechanics", "popularmechanics.com"),
    ("Bob Vila", "bobvila.com"),
    ("Forbes", "forbes.com"),
]


def _api_error_message(response) -> str:
    try:
        return response.json()["error"]["message"]
    except Exception:
        return f"HTTP {response.status_code}"


class EditorialSearchProvider(PlatformProvider):
    platform_name = "Editorial Coverage"
    credential_fields = {
        "api_key": "API Key",
        "engine_id": "Search Engine ID (cx)",
    }

    def fetch_brand_presence(self, brand: str) -> dict:
        base = {"brand": brand, "platform": self.platform_name}
        api_key = self.credentials.get("api_key", "")
        engine_id = self.credentials.get("engine_id", "")
        if not api_key or not engine_id:
            return {**base, "error": "Google Custom Search not configured — "
                                     "add API key + engine ID in Settings."}

        per_site_raw: list[tuple[str, str, dict]] = []
        for label, domain in EDITORIAL_SITES:
            try:
                resp = requests.get(_SEARCH_URL, params={
                    "key": api_key, "cx": engine_id,
                    "q": f'"{brand}" generator site:{domain}',
                    "num": 3,
                }, timeout=_TIMEOUT)
            except requests.RequestException as exc:
                return {**base, "error": f"Editorial search failed: {exc}"}
            if resp.status_code != 200:
                # Abort the brand on the first API error rather than keep
                # going — the realistic failure is quota exhaustion mid-run,
                # and continuing would produce a silently-undercounted
                # brand that gap analysis then misreads as a real gap.
                message = _api_error_message(resp)
                if resp.status_code == 403 and "quota" not in message.lower():
                    # Real-testing failure mode: API enabled but the key's
                    # "API restrictions" in Google Cloud Credentials don't
                    # include Custom Search API (or enablement hasn't
                    # propagated yet).
                    message += (" — if the API is enabled, check that the key's "
                                "'API restrictions' in Google Cloud Credentials "
                                "include Custom Search API, then retry in a few "
                                "minutes.")
                return {**base, "error": f"Editorial search failed on {label}: {message}"}
            per_site_raw.append((label, domain, resp.json()))
            time.sleep(0.25)  # polite pacing under the API's per-second limits

        return {**base, **parse_editorial_results(per_site_raw), "error": ""}


def parse_editorial_results(per_site_raw: list[tuple[str, str, dict]]) -> dict:
    """
    Pure transform of raw (label, domain, API payload) triples into the
    stored metric shape — separated from the network calls so tests
    exercise the real parsing against canned payloads without any HTTP.
    """
    per_site = []
    for label, domain, payload in per_site_raw:
        try:
            results = int(payload.get("searchInformation", {}).get("totalResults", 0))
        except (TypeError, ValueError):
            results = 0
        items = payload.get("items", []) or []
        top = items[0] if items else {}
        per_site.append({
            "site": label,
            "domain": domain,
            "results": results,
            "top_title": top.get("title", ""),
            "top_url": top.get("link", ""),
        })

    covered = [s for s in per_site if s["results"] > 0]
    strongest = max(per_site, key=lambda s: s["results"], default=None)
    return {
        "per_site": per_site,
        "sites_with_coverage": len(covered),
        "sites_checked": len(per_site),
        "total_results": sum(s["results"] for s in per_site),
        "strongest_site": (strongest["site"]
                           if strongest and strongest["results"] > 0 else ""),
    }

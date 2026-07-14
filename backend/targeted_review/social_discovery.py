"""
Brand social-link discovery (#25 follow-up, user request 2026-07-06):
scrape each brand's manufacturer website (already in Knowledge) for its
official social profiles — most importantly the YouTube CHANNEL, which
unlocks cheap, rich channel metrics (subscribers, uploads, comments) that
search queries can't provide and that cost ~3 quota units instead of ~400.
"""
import re

import requests
from bs4 import BeautifulSoup

from backend.price_comparison.google_shopping_scraper import _HEADERS

_TIMEOUT = 15

# platform key -> compiled matcher for profile-shaped URLs (not share links)
_SOCIAL_PATTERNS = {
    "youtube": re.compile(
        r"https?://(?:www\.)?youtube\.com/(?:channel/UC[\w-]+|@[\w.\-]+|user/[\w.\-]+|c/[\w.\-]+)",
        re.IGNORECASE),
    "facebook": re.compile(
        r"https?://(?:www\.)?facebook\.com/(?!sharer|share|plugins)[\w.\-]+", re.IGNORECASE),
    "instagram": re.compile(
        r"https?://(?:www\.)?instagram\.com/[\w.\-]+", re.IGNORECASE),
    "x": re.compile(
        r"https?://(?:www\.)?(?:twitter|x)\.com/(?!intent|share)[\w]+", re.IGNORECASE),
    "tiktok": re.compile(
        r"https?://(?:www\.)?tiktok\.com/@[\w.\-]+", re.IGNORECASE),
    "linkedin": re.compile(
        r"https?://(?:www\.)?linkedin\.com/company/[\w.\-]+", re.IGNORECASE),
}


def extract_social_links(html: str) -> dict[str, str]:
    """Pure extraction of the FIRST profile-shaped link per platform from a
    page's anchors — separated from fetching so tests never touch HTTP."""
    soup = BeautifulSoup(html or "", "html.parser")
    hrefs = [a.get("href", "") for a in soup.find_all("a", href=True)]
    found: dict[str, str] = {}
    for href in hrefs:
        for platform, pattern in _SOCIAL_PATTERNS.items():
            if platform in found:
                continue
            match = pattern.match(href.strip())
            if match:
                found[platform] = match.group(0)
    return found


_CHANNEL_ID_PATTERNS = (
    re.compile(r'"externalId":"(UC[\w-]{10,})"'),
    re.compile(r'youtube\.com/channel/(UC[\w-]{10,})'),
    re.compile(r'itemprop="identifier" content="(UC[\w-]{10,})"'),
)


def resolve_youtube_channel_url(url: str) -> str:
    """
    Canonicalize any YouTube channel URL form to /channel/UC… by fetching
    the channel page once and reading its embedded channel id. Exists
    because legacy /c/NAME custom URLs have NO Data API lookup — and the
    target brand's own channel (youtube.com/c/FirmanPowerEquipment) uses
    exactly that form, so without this its Ch. Subs could never populate
    (found in the user's v1.0 test pass, item 6.3; extraction patterns
    verified live against the real Firman page). Returns "" on any
    failure — callers keep the original URL.
    """
    if not url or "/channel/UC" in url:
        return url or ""
    try:
        resp = requests.get(url, headers={**_HEADERS,
                                          "Accept-Language": "en-US,en;q=0.9"},
                            timeout=_TIMEOUT)
        if resp.status_code != 200:
            return ""
        for pattern in _CHANNEL_ID_PATTERNS:
            match = pattern.search(resp.text)
            if match:
                return f"https://www.youtube.com/channel/{match.group(1)}"
    except requests.RequestException:
        pass
    return ""


def discover_socials_for_website(website: str) -> dict:
    """Fetch a brand homepage and extract social links. In-band error shape
    like every other collector — a dead site must not sink the batch."""
    url = website.strip()
    if not url:
        return {"links": {}, "error": "No website on record for this brand."}
    if not url.lower().startswith("http"):
        url = "https://" + url
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return {"links": {}, "error": f"Site returned HTTP {resp.status_code}."}
    except requests.RequestException as exc:
        return {"links": {}, "error": f"Fetch failed: {exc}"}

    links = extract_social_links(resp.text)
    # Store the API-resolvable canonical form when the site links a legacy
    # /c/ custom URL (one extra GET, only for that form).
    youtube = links.get("youtube", "")
    if youtube and "/c/" in youtube:
        canonical = resolve_youtube_channel_url(youtube)
        if canonical:
            links["youtube"] = canonical
    return {"links": links, "error": ""}

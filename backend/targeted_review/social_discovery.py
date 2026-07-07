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
    return {"links": extract_social_links(resp.text), "error": ""}

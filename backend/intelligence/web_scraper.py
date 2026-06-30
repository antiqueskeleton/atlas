"""
On-page SEO scraper for competitor domain analysis.

Scrapes a domain's homepage and extracts signals that are freely available
without any paid API: title tag, meta description, heading structure,
keyword frequency, HTTPS status, sitemap presence, and load time.
"""

import re
import time
from collections import Counter

import requests
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_STOP_WORDS = {
    "about", "after", "also", "back", "been", "before", "between",
    "both", "came", "come", "could", "does", "each", "even", "from",
    "give", "good", "great", "have", "here", "home", "into", "just",
    "keep", "like", "make", "more", "most", "much", "need", "only",
    "other", "over", "same", "shop", "some", "such", "than", "that",
    "their", "them", "then", "there", "they", "this", "time", "very",
    "want", "well", "were", "what", "when", "where", "which", "will",
    "with", "would", "your",
}


def scrape_domain(domain: str) -> dict:
    """
    Fetch a domain's homepage and extract on-page SEO signals.

    Returns a dict with keys:
        title, meta_description, h1s, h2s, top_keywords,
        has_schema, has_sitemap, is_https, load_ms, status_code, error
    """
    url = domain.strip()
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    # Strip trailing path so we always hit the homepage
    from urllib.parse import urlparse
    parsed = urlparse(url)
    homepage = f"{parsed.scheme}://{parsed.netloc}/"

    result: dict = {
        "title": "",
        "meta_description": "",
        "h1s": [],
        "h2s": [],
        "top_keywords": "",
        "has_schema": False,
        "has_sitemap": False,
        "is_https": homepage.startswith("https://"),
        "load_ms": 0,
        "status_code": 0,
        "error": "",
    }

    # ── Fetch homepage ────────────────────────────────────────────────────────
    t0 = time.time()
    try:
        resp = requests.get(homepage, headers=_HEADERS, timeout=12, allow_redirects=True)
        result["load_ms"] = int((time.time() - t0) * 1000)
        result["status_code"] = resp.status_code
        result["is_https"] = resp.url.startswith("https://")
        if resp.status_code >= 400:
            result["error"] = f"HTTP {resp.status_code}"
            return result
        html = resp.text
    except requests.exceptions.Timeout:
        result["error"] = "Timeout"
        return result
    except Exception as exc:
        result["error"] = str(exc)[:120]
        return result

    # ── Parse ─────────────────────────────────────────────────────────────────
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    result["title"] = title_tag.get_text(strip=True)[:200] if title_tag else ""

    meta = soup.find("meta", attrs={"name": "description"}) or \
           soup.find("meta", attrs={"property": "og:description"})
    result["meta_description"] = (meta.get("content", "") or "")[:300] if meta else ""

    result["h1s"] = [h.get_text(strip=True) for h in soup.find_all("h1")][:5]
    result["h2s"] = [h.get_text(strip=True) for h in soup.find_all("h2")][:10]

    result["has_schema"] = bool(
        soup.find("script", attrs={"type": "application/ld+json"})
    )

    # Keyword frequency from visible text (strip scripts/styles first)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    body_text = soup.get_text(separator=" ").lower()
    words = re.findall(r"\b[a-z]{4,}\b", body_text)
    words = [w for w in words if w not in _STOP_WORDS]
    top = [w for w, _ in Counter(words).most_common(20)]
    result["top_keywords"] = ", ".join(top)

    # ── Sitemap check (HEAD only — no extra body download) ────────────────────
    sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
    try:
        sr = requests.head(sitemap_url, headers=_HEADERS, timeout=6, allow_redirects=True)
        result["has_sitemap"] = sr.status_code < 400
    except Exception:
        result["has_sitemap"] = False

    return result

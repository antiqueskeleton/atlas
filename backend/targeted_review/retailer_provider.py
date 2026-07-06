"""
Retailer product-listing data (review count, star rating, price) from
user-pasted product page URLs (#25, build-sequence step 3).

This is the pragmatic near-term path to real Amazon/Home Depot/Lowe's/
Walmart review data: Amazon's official Product Advertising API requires an
active Associates affiliate sales history the brand doesn't have, so
instead the user curates product URLs per brand and Atlas extracts the
listing's own structured data. Extends the JSON-LD approach already proven
in backend/price_comparison/google_shopping_scraper.py's
scrape_url_for_price(), adding aggregateRating extraction (that function
only pulls price).

Fetch strategy: plain requests first; for Amazon (which serves bot walls to
plain requests far more aggressively than the other retailers) fall back to
cloudscraper — already a project dependency via requirements.txt. When a
page still can't be read, the failure is reported in-band per listing, not
raised: one blocked URL must not sink a collection run over the rest.
"""
from __future__ import annotations

import json
import random
import re
import time

import requests
from bs4 import BeautifulSoup

from backend.price_comparison.google_shopping_scraper import _HEADERS, _retailer_from_url
from backend.targeted_review.base_platform_provider import PlatformProvider

_TIMEOUT = 20
_COUNT_RE = re.compile(r"([\d,]+)")
_RATING_RE = re.compile(r"(\d\.?\d?)\s*out of\s*5")


class RetailerListingProvider(PlatformProvider):
    platform_name = "Retail Listings"
    credential_fields = {}  # no API — works from user-saved product URLs

    def fetch_brand_presence(self, brand: str) -> dict:
        # This platform is URL-driven, not brand-query-driven: the service
        # iterates the user's saved product URLs for each brand and calls
        # fetch_listing() per URL, then aggregates. Kept only to satisfy the
        # PlatformProvider contract.
        return {"brand": brand, "platform": self.platform_name,
                "error": "Retail Listings collects from saved product URLs, "
                         "not brand search — add product URLs on the Targeted Review page."}

    def fetch_listing(self, url: str) -> dict:
        """Fetch one product page and extract listing metrics."""
        html = _fetch_html(url)
        if not html:
            return {"url": url, "retailer": _retailer_from_url(url),
                    "error": "Page could not be fetched — the retailer may be "
                             "blocking automated access."}
        return parse_listing_html(html, url)


def _fetch_html(url: str) -> str:
    """requests first; cloudscraper fallback for Amazon's bot wall."""
    time.sleep(random.uniform(0.8, 1.8))  # polite pacing between listings
    html = ""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code == 200:
            html = resp.text
    except requests.RequestException:
        pass

    # Amazon serves CAPTCHA interstitials to plain requests — detectable by
    # the absence of any product markers. Retry once through cloudscraper.
    if "amazon." in url.lower():
        if "captcha" in html.lower() or not _looks_like_product(html):
            try:
                import cloudscraper
                scraper = cloudscraper.create_scraper()
                resp = scraper.get(url, timeout=30)
                if resp.status_code == 200 and _looks_like_product(resp.text):
                    html = resp.text
            except Exception:
                pass
        # Still an interstitial after the retry → report as blocked rather
        # than letting the parser misread a CAPTCHA page as "no reviews".
        return html if _looks_like_product(html) else ""

    # Non-Amazon: return whatever came back — a page without structured-data
    # markers should surface as "no rating data found" (a parsing outcome),
    # not be silently misreported as a blocked fetch.
    return html


def _looks_like_product(html: str) -> bool:
    if not html or len(html) < 2000:
        return False
    lowered = html.lower()
    return ('"@type"' in lowered and "product" in lowered) \
        or "productTitle" in html or "acrCustomerReviewText" in html \
        or "itemprop=" in lowered


def parse_listing_html(html: str, url: str) -> dict:
    """
    Pure extraction of listing metrics from product-page HTML — separated
    from the network fetch so tests exercise the real parsing against saved
    page samples without any HTTP.

    Returns: {url, retailer, title, rating, review_count, price, error}
    with rating/review_count/price as None when genuinely absent — absence
    is reported, never guessed (same "confirmed data only" rule the price
    scraper follows).
    """
    soup = BeautifulSoup(html, "html.parser")
    result = {
        "url": url,
        "retailer": _retailer_from_url(url),
        "title": "",
        "rating": None,
        "review_count": None,
        "price": None,
        "error": "",
    }

    # ── Strategy 1: JSON-LD Product schema (Home Depot/Lowe's/Walmart) ──────
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for item in _iter_products(data):
            if not result["title"]:
                result["title"] = str(item.get("name", ""))[:200]
            agg = item.get("aggregateRating") or {}
            if isinstance(agg, dict):
                result["rating"] = result["rating"] or _to_float(agg.get("ratingValue"))
                result["review_count"] = result["review_count"] or _to_int(
                    agg.get("reviewCount") or agg.get("ratingCount"))
            offers = item.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            if isinstance(offers, dict):
                result["price"] = result["price"] or _to_float(
                    offers.get("price") or offers.get("lowPrice"))

    # ── Strategy 2: Amazon-specific selectors (no JSON-LD on Amazon) ────────
    if result["review_count"] is None:
        count_el = soup.select_one("#acrCustomerReviewText")
        if count_el:
            m = _COUNT_RE.search(count_el.get_text())
            if m:
                result["review_count"] = int(m.group(1).replace(",", ""))
    if result["rating"] is None:
        pop = soup.select_one("#acrPopover")
        text = (pop.get("title", "") if pop else "") or ""
        if not text:
            alt = soup.select_one("span[data-hook='rating-out-of-text']")
            text = alt.get_text() if alt else ""
        m = _RATING_RE.search(text)
        if m:
            result["rating"] = float(m.group(1))
    if not result["title"]:
        title_el = soup.select_one("#productTitle")
        if title_el:
            result["title"] = title_el.get_text(strip=True)[:200]
    if result["price"] is None:
        price_el = soup.select_one(".a-offscreen")
        if price_el:
            m = re.search(r"\$\s*([\d,]+\.?\d{0,2})", price_el.get_text())
            if m:
                result["price"] = _to_float(m.group(1).replace(",", ""))

    # ── Strategy 3: generic microdata fallback ──────────────────────────────
    if result["rating"] is None:
        el = soup.select_one("[itemprop='ratingValue']")
        if el:
            result["rating"] = _to_float(el.get("content") or el.get_text())
    if result["review_count"] is None:
        el = soup.select_one("[itemprop='reviewCount'], [itemprop='ratingCount']")
        if el:
            result["review_count"] = _to_int(el.get("content") or el.get_text())

    if result["rating"] is None and result["review_count"] is None:
        result["error"] = ("No rating/review data found in the page — the listing "
                           "may render reviews via JavaScript only.")
    return result


def _iter_products(data):
    """Yield every schema.org Product object in a JSON-LD blob (handles
    top-level lists, @graph containers, and plain objects)."""
    items = data if isinstance(data, list) else [data]
    for item in items:
        if not isinstance(item, dict):
            continue
        if "@graph" in item and isinstance(item["@graph"], list):
            yield from _iter_products(item["@graph"])
        if "Product" in str(item.get("@type", "")):
            yield item


def _to_float(value) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _to_int(value) -> int | None:
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return None

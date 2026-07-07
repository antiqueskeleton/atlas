"""
Best Buy retail presence via the official Products API (#98) — the one
major generator retailer with a real, free, keyed API (developer.bestbuy.com),
unlike Lowe's and Home Depot which hard-block scraping (confirmed 2026-07-06)
and Amazon whose Product Advertising API needs affiliate sales history.

Per brand: one search query for the brand + generator, filtered client-side
with the same word-boundary matching as the core pipeline (#87 — 'CAT'
must not match 'category' in product names), aggregating listing count,
total customer reviews, and review-weighted average rating.
"""
import requests

from backend.targeted_review.base_platform_provider import PlatformProvider
from backend.visibility.brand_matcher import text_contains_term

_PRODUCTS_URL = "https://api.bestbuy.com/v1/products"
_TIMEOUT = 20


class BestBuyProvider(PlatformProvider):
    platform_name = "Best Buy"
    credential_fields = {"api_key": "API Key"}

    def fetch_brand_presence(self, brand: str) -> dict:
        base = {"brand": brand, "platform": self.platform_name}
        api_key = self.credentials.get("api_key", "")
        if not api_key:
            return {**base, "error": "No Best Buy API key configured — free at "
                                     "developer.bestbuy.com, add it in Settings."}

        # (search=word&search=word...) — every brand word plus "generator".
        words = [w for w in brand.split() if w.strip("&")] + ["generator"]
        query = "&".join(f"search={w.lower()}" for w in words)
        try:
            resp = requests.get(
                f"{_PRODUCTS_URL}(({query}))",
                params={
                    "apiKey": api_key, "format": "json", "pageSize": 100,
                    "show": "name,customerReviewAverage,customerReviewCount,salePrice",
                },
                timeout=_TIMEOUT,
            )
        except requests.RequestException as exc:
            return {**base, "error": f"Best Buy request failed: {exc}"}
        if resp.status_code != 200:
            detail = resp.text[:150]
            if resp.status_code == 403:
                detail = "invalid or inactive API key"
            return {**base, "error": f"Best Buy API returned HTTP "
                                     f"{resp.status_code} — {detail}"}

        try:
            products = resp.json().get("products", [])
        except ValueError:
            return {**base, "error": "Best Buy returned an unreadable response."}

        return {**base, **parse_bestbuy_products(products, brand), "error": ""}


def parse_bestbuy_products(products: list[dict], brand: str) -> dict:
    """
    Pure transform — filter to products whose NAME actually contains the
    brand (word-boundary; Best Buy's search matches loosely) and aggregate.
    Rating averaged weighted by each product's review count, same rule as
    the retail-listings aggregation.
    """
    brand_lower = brand.lower()
    matched = []
    for product in products:
        name = product.get("name") or ""
        if not text_contains_term(name.lower(), brand_lower):
            continue
        try:
            reviews = int(product.get("customerReviewCount") or 0)
        except (TypeError, ValueError):
            reviews = 0
        try:
            rating = float(product.get("customerReviewAverage") or 0) or None
        except (TypeError, ValueError):
            rating = None
        try:
            price = float(product.get("salePrice") or 0) or None
        except (TypeError, ValueError):
            price = None
        matched.append({"name": name[:120], "reviews": reviews,
                        "rating": rating, "price": price})

    matched.sort(key=lambda p: -p["reviews"])
    rated = [(p["rating"], p["reviews"] or 1) for p in matched if p["rating"]]
    avg_rating = (round(sum(r * w for r, w in rated) / sum(w for _, w in rated), 2)
                  if rated else None)
    return {
        "listings_found": len(matched),
        "total_reviews": sum(p["reviews"] for p in matched) or None,
        "avg_rating": avg_rating,
        "top_products": matched[:10],
    }

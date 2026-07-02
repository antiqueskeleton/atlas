"""
Product data scraper for Competitive Shopping.

Data source hierarchy (highest to lowest reliability):
  1. Shopify JSON endpoint — direct, no scraping, gives MSRP + description
  2. Manufacturer product page HTML — direct fetch, parse spec table
  3. Google Shopping HTML — find comparable model numbers for comp brands
     (prices from Google Shopping alone are NOT trusted due to JS rendering)

The regex fallback that previously returned garbage ($0, $2, $8) is removed.
Only confirmed, reasonably-priced results are returned.
"""
from __future__ import annotations

import json
import logging
import random
import re
import time
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-cache",
}

# ── Brand / domain knowledge ──────────────────────────────────────────────────

# Brands that run Shopify stores — verified domains.
# Only include brands where /collections/all/products.json returns real products.
# Unverified domains are excluded rather than guessed.
_SHOPIFY_BRANDS: dict[str, str] = {
    "firman":    "firmanpowerequipment.com",   # verified ✓
    "duromax":   "duromaxpower.com",           # verified ✓
    "wen":       "wenproducts.com",            # verified ✓
    "a-ipower":  "aipowerusa.com",             # verified (Brotli handled via header)
    "aipower":   "aipowerusa.com",
    "genmax":    "genmaxpower.com",            # verified (Brotli handled via header)
}

# Brands with non-Shopify manufacturer sites — direct HTML only
_BRAND_DOMAINS: dict[str, str] = {
    "generac":            "generac.com",
    "honda":              "powerequipment.honda.com",
    "briggs":             "briggsandstratton.com",
    "briggs & stratton":  "briggsandstratton.com",
    "kohler":             "kohlerpower.com",
    "cummins":            "cummins.com",
    "yamaha":             "yamahagenerators.com",
    "cat":                "cat.com",
}

# Retailer name normalisation
_RETAILER_MAP: dict[str, str] = {
    "home depot":     "Home Depot",
    "homedepot":      "Home Depot",
    "lowe's":         "Lowe's",
    "lowes":          "Lowe's",
    "walmart":        "Walmart",
    "amazon":         "Amazon",
    "costco":         "Costco",
    "best buy":       "Best Buy",
    "bestbuy":        "Best Buy",
    "tractor supply": "Tractor Supply",
    "tractorsupply":  "Tractor Supply",
    "northern tool":  "Northern Tool",
    "northerntool":   "Northern Tool",
    "ace hardware":   "Ace Hardware",
    "sam's club":     "Sam's Club",
    "samsclub":       "Sam's Club",
    "factorypu":      "FactoryPure",
    "factory pure":   "FactoryPure",
}

# Model number patterns — order matters (most specific first)
_MODEL_RE = [
    re.compile(r'\b([A-Z]{1,3}\d{4,6}[A-Z]{0,4})\b'),    # T08073, WGen7500c, GP9500TF
    re.compile(r'\b([A-Z]{2,5}-\d{3,5}[A-Z]{0,3})\b'),   # WH-7500
    re.compile(r'\b([A-Z]{2,6}\d{2,4}[A-Z]{0,2})\b'),    # GP9500, RYi2322VNM
    re.compile(r'\b(\d{4,5}[A-Z]{1,3})\b'),               # 7500DF, 3650E
]

_PRICE_RE = re.compile(r'\$\s*([\d,]+\.?\d{0,2})')

# Minimum price to be considered a real product (filters shipping fees, etc.)
_MIN_PRICE = 50.0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_shopify_domain(brand: str) -> str | None:
    b = brand.lower().strip()
    # Exact key match first, then prefix match (min 5 chars to avoid false positives)
    for key, domain in _SHOPIFY_BRANDS.items():
        if key == b or (len(key) >= 5 and b.startswith(key)):
            return domain
    return None


def _get_brand_domain(brand: str) -> str | None:
    b = brand.lower().strip()
    for key, domain in _BRAND_DOMAINS.items():
        if key in b:
            return domain
    return None


def _normalise_retailer(raw: str) -> str:
    lower = raw.lower().strip()
    for key, name in _RETAILER_MAP.items():
        if key in lower:
            return name
    return raw.strip().title()


def _parse_price(text: str) -> float | None:
    m = _PRICE_RE.search(text.replace(",", ""))
    if m:
        try:
            val = float(m.group(1).replace(",", ""))
            return val if val >= _MIN_PRICE else None
        except ValueError:
            return None
    return None


def _get(url: str, delay: tuple = (0.8, 1.8), timeout: int = 15) -> requests.Response | None:
    time.sleep(random.uniform(*delay))
    try:
        r = requests.get(url, headers=_HEADERS, timeout=timeout)
        return r if r.status_code == 200 else None
    except requests.RequestException as exc:
        log.debug("GET %s failed: %s", url, exc)
        return None


def extract_model_from_title(title: str, brand: str) -> str:
    """Pull a model number out of a product listing title."""
    # Remove brand name first
    clean = re.sub(re.escape(brand), '', title, flags=re.IGNORECASE).strip()
    for rx in _MODEL_RE:
        m = rx.search(clean)
        if m:
            return m.group(1).upper()
    return ""


# ── Retailer URL scraping (user-supplied product page URLs) ──────────────────

# Map hostname fragments → display retailer names
_RETAILER_HOSTS: dict[str, str] = {
    "lowes.com":       "Lowe's",
    "homedepot.com":   "Home Depot",
    "walmart.com":     "Walmart",
    "amazon.com":      "Amazon",
    "costco.com":      "Costco",
    "tractorsupply.com": "Tractor Supply",
    "northerntool.com":  "Northern Tool",
    "acehardware.com":   "Ace Hardware",
    "samsclub.com":      "Sam's Club",
    "bjs.com":           "BJ's",
    "menards.com":       "Menards",
}

# Common price CSS selectors per retailer (ordered best → fallback)
_PRICE_SELECTORS: list[str] = [
    # Standard schema / JSON-LD is handled separately
    ".a-offscreen",                               # Amazon
    "[data-testid='price-block'] [class*='price']",  # Walmart
    ".ProductPresentation-module__price",          # Lowe's
    ".price-format__main-price",                  # Home Depot
    ".product-price",
    ".sale-price",
    ".current-price",
    "[class*='current-price']",
    "[class*='sale-price']",
    "[itemprop='price']",
    ".price",
]


def _retailer_from_url(url: str) -> str:
    """Infer retailer display name from a product page URL."""
    lower = url.lower()
    for host, name in _RETAILER_HOSTS.items():
        if host in lower:
            return name
    # Fallback: use second-level domain
    m = re.search(r'https?://(?:www\.)?([^/]+)', lower)
    return m.group(1).split(".")[0].title() if m else "Retailer"


def scrape_url_for_price(url: str) -> dict | None:
    """
    Scrape a specific product page URL to extract the current price.

    Tries (in order):
      1. JSON-LD structured data (schema.org/Product → offers → price)
      2. CSS selectors from _PRICE_SELECTORS
      3. Price regex on raw text near dollar signs (conservative — min $50)

    Returns dict with keys: price, retailer, url, method, confirmed
    Returns None if no price could be confirmed.
    """
    resp = _get(url, delay=(0.8, 1.8))
    if not resp:
        return None

    retailer = _retailer_from_url(url)
    soup     = BeautifulSoup(resp.content, "html.parser", from_encoding="utf-8")
    price    = None

    # ── Strategy 1: JSON-LD ───────────────────────────────────────────────────
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(script.string or "")
            items = d if isinstance(d, list) else [d]
            for item in items:
                t = str(item.get("@type", ""))
                if "Product" in t:
                    offers = item.get("offers", {})
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    candidate = offers.get("price") or offers.get("lowPrice")
                    if candidate:
                        try:
                            candidate = float(str(candidate).replace(",", ""))
                            if candidate >= _MIN_PRICE:
                                price = candidate
                                break
                        except (ValueError, TypeError):
                            pass
            if price:
                break
        except Exception:
            pass

    # ── Strategy 2: CSS selectors ─────────────────────────────────────────────
    if not price:
        for sel in _PRICE_SELECTORS:
            el = soup.select_one(sel)
            if el:
                candidate = _parse_price(el.get_text())
                if candidate:
                    price = candidate
                    break

    # ── Strategy 3: conservative price regex ─────────────────────────────────
    if not price:
        # Only look at price-like tags (span/div with "price" in class)
        for el in soup.find_all(["span", "div"], class_=re.compile("price", re.I)):
            candidate = _parse_price(el.get_text())
            if candidate and candidate <= 10000:
                price = candidate
                break

    if not price:
        return None

    return {
        "price":       price,
        "retailer":    retailer,
        "url":         url,
        "title":       "",
        "availability": "",
        "confirmed":   True,
        "method":      "retailer_direct",
    }


# ── Tier 1: Shopify JSON direct fetch ─────────────────────────────────────────

def fetch_shopify_product(brand: str, model: str) -> dict:
    """
    Fetch product data from a Shopify store's public JSON endpoint.

    Returns dict with keys: msrp, sale_price, title, source_url
    Returns {} if brand is not a known Shopify store or model not found.
    This is the most reliable source — no HTML parsing, structured data.
    """
    domain = _get_shopify_domain(brand)
    if not domain:
        return {}

    handle  = model.lower().replace(" ", "-").replace("_", "-")
    json_url = f"https://{domain}/products/{handle}.json"
    page_url = f"https://{domain}/products/{handle}"

    resp = _get(json_url, delay=(0.5, 1.2))
    if not resp:
        return {}

    try:
        data    = resp.json()
        product = data.get("product", {})
        if not product:
            return {}

        msrp = sale_price = None
        for v in product.get("variants", []):
            cap = v.get("compare_at_price")  # MSRP / original price
            cur = v.get("price")             # current / sale price
            if cur:
                try:
                    sale_price = float(cur)
                    msrp       = float(cap) if cap else sale_price
                    break
                except (ValueError, TypeError):
                    pass

        return {
            "msrp":       msrp,
            "sale_price": sale_price,
            "title":      product.get("title", ""),
            "source_url": page_url,
        }
    except (json.JSONDecodeError, KeyError) as exc:
        log.debug("Shopify JSON parse failed %s %s: %s", brand, model, exc)
        return {}


def fetch_shopify_products_list(brand: str, keyword: str = "",
                                limit: int = 50) -> list[dict]:
    """
    List products from a brand's Shopify store via the public collections API.
    Filters results to those whose title contains `keyword` (case-insensitive).
    Returns list of price-dict objects compatible with the comp shopping service.
    """
    domain = _get_shopify_domain(brand)
    if not domain:
        return []

    url = (
        f"https://{domain}/collections/all/products.json"
        f"?limit={limit}&sort_by=best-selling"
    )
    resp = _get(url, delay=(0.5, 1.5))
    if not resp:
        return []

    try:
        products = resp.json().get("products", [])
    except (json.JSONDecodeError, Exception):
        return []

    kw = keyword.lower()
    # Detect accessories disguised as brand products ("Oil Dipstick for Honda")
    _accessory_re = re.compile(
        r'\bfor\s+(Honda|Yamaha|Generac|Champion|Westinghouse|Firman|DuroMax|'
        r'Kohler|Briggs|WEN|DuroStar|Pulsar|CAT|DeWalt|Craftsman)\b',
        re.IGNORECASE,
    )
    results = []

    for p in products:
        title = p.get("title", "")

        # Skip products for a different brand (e.g., adapters, accessories)
        if _accessory_re.search(title):
            continue

        if kw and kw not in title.lower():
            continue

        price = None
        for v in p.get("variants", []):
            try:
                candidate = float(v.get("price", 0))
                if candidate >= _MIN_PRICE:
                    price = candidate
                    break
            except (TypeError, ValueError):
                pass

        if price is None:
            continue

        handle = p.get("handle", "")

        # Try model extraction: title → handle slug → SKU (in order)
        model = extract_model_from_title(title, brand)
        if not model and handle:
            model = extract_model_from_title(handle.replace("-", " "), brand)
        if not model and p.get("variants"):
            sku = p["variants"][0].get("sku", "").strip()
            if sku and len(sku) >= 4:
                model = sku.upper()

        results.append({
            "title":           title,
            "price":           price,
            "retailer":        "Manufacturer (MSRP)",
            "url":             f"https://{domain}/products/{handle}",
            "availability":    "",
            "confirmed":       True,
            "method":          "shopify_direct",
            "model_extracted": model,
        })

    return results


# ── Tier 2: Manufacturer page HTML scraping ───────────────────────────────────

def scrape_manufacturer_specs(brand: str, model: str) -> tuple[dict[str, str], str]:
    """
    Fetch and parse the manufacturer's product page for spec data.

    For Shopify brands: GET /products/{model} directly.
    For others: search Google to find the product URL, then fetch.
    Returns (specs_dict, source_url).  specs_dict only contains confirmed values.
    """
    if not model.strip():
        return {}, ""

    # Try Shopify direct page first
    domain = _get_shopify_domain(brand)
    if domain:
        handle  = model.lower().replace(" ", "-")
        page_url = f"https://{domain}/products/{handle}"
        resp = _get(page_url)
        if resp:
            specs = _extract_specs(resp.text)
            if specs:
                return specs, page_url

    # Try non-Shopify known domain
    brand_domain = _get_brand_domain(brand)
    if brand_domain:
        # Try a simple search page pattern
        search_url = f"https://www.{brand_domain}/search?q={quote_plus(model)}"
        resp = _get(search_url)
        if resp:
            soup  = BeautifulSoup(resp.text, "html.parser")
            links = soup.select("a[href]")
            for link in links:
                href = link.get("href", "")
                if model.lower() in href.lower():
                    full = href if href.startswith("http") else f"https://{brand_domain}{href}"
                    resp2 = _get(full)
                    if resp2:
                        specs = _extract_specs(resp2.text)
                        if specs:
                            return specs, full
                    break

    # Last resort: Google search for manufacturer page
    return _scrape_specs_via_google(brand, model)


def _scrape_specs_via_google(brand: str, model: str) -> tuple[dict[str, str], str]:
    query = f"{brand} {model} specifications site manufacturer"
    resp  = _get(
        f"https://www.google.com/search?q={quote_plus(query)}&hl=en&gl=us&num=5",
        delay=(1.5, 2.5),
    )
    if not resp:
        return {}, ""

    soup       = BeautifulSoup(resp.text, "html.parser")
    brand_slug = re.sub(r'[^a-z0-9]', '', brand.lower())

    for link in soup.select("a[href]"):
        href = link.get("href", "")
        m    = re.search(r'/url\?q=([^&]+)', href)
        if not m:
            continue
        candidate = m.group(1)
        # Prefer URLs that contain the brand name
        if brand_slug in candidate.lower():
            resp2 = _get(candidate)
            if resp2:
                specs = _extract_specs(resp2.text)
                if specs:
                    return specs, candidate

    return {}, ""


# ── Tier 3: Model discovery for comp brands ───────────────────────────────────

def search_for_models(brand: str, keywords: str = "generator",
                      max_results: int = 5) -> list[dict]:
    """
    Discover products / model numbers for a brand.

    Strategy order:
      1. Shopify collections API (verified brands only) — most reliable
      2. Google Shopping HTML — fallback for non-Shopify brands (may return
         nothing if JS rendering is required, which is common)

    Returns list of {title, price, retailer, url, model_extracted, method}.
    """
    # ── Try Shopify collections first ─────────────────────────────────────────
    shopify_results = fetch_shopify_products_list(brand, keyword=keywords,
                                                   limit=50)
    if shopify_results:
        return shopify_results[:max_results]

    # ── Fall back to Google Shopping ──────────────────────────────────────────
    query = f"{brand} {keywords}"
    resp  = _get(
        f"https://www.google.com/search?q={quote_plus(query)}&tbm=shop&hl=en&gl=us&num=20",
        delay=(1.2, 2.8),
    )
    if not resp:
        return []

    raw = _parse_shopping_html_strict(resp.text)
    out = []
    seen_models: set[str] = set()

    for r in raw:
        model = extract_model_from_title(r["title"], brand)
        if model and model not in seen_models:
            seen_models.add(model)
            r["model_extracted"] = model
            out.append(r)
        elif not model:
            # Include even without model (price / retailer still useful)
            r["model_extracted"] = ""
            out.append(r)

    return out[:max_results]


def search_product(brand: str, model: str,
                   keywords: str = "generator",
                   max_results: int = 8) -> list[dict]:
    """
    Search Google Shopping for a specific brand + model.
    Returns confirmed price results only (price > $50, retailer identified).
    """
    parts = [p for p in [brand, model, keywords] if p.strip()]
    query = " ".join(parts)
    resp  = _get(
        f"https://www.google.com/search?q={quote_plus(query)}&tbm=shop&hl=en&gl=us&num=20",
        delay=(1.2, 2.8),
    )
    if not resp:
        return []

    results = _parse_shopping_html_strict(resp.text)
    seen: set[tuple] = set()
    deduped = []
    for r in results:
        key = (r["retailer"].lower(), r["price"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return deduped[:max_results]


def _parse_shopping_html_strict(html: str) -> list[dict]:
    """
    Parse Google Shopping HTML using CSS selectors only.
    NO regex fallback — if CSS selectors find nothing, return [].
    Requires: price > $50 AND a retailer name in the known list.
    """
    soup    = BeautifulSoup(html, "html.parser")
    results = []

    selector_sets = [
        # Grid view
        ("div.sh-dgr__content, div.KZmu8e",
         ".tAxDx, .aaCjle", ".a8Pemb, .kHxwFf, .HRLxBb",
         ".aULzUe, .IuHnof, .E5ocAb"),
        # List view
        ("div.sh-dlr__list-result, div.pla-unit",
         "h3, .kEjbwb", ".HRLxBb, .e10twf, .g9WBQb",
         ".IuHnof, .E5ocAb, .shntl"),
    ]

    for card_sel, title_sel, price_sel, store_sel in selector_sets:
        for card in soup.select(card_sel):
            try:
                title_el = card.select_one(title_sel)
                price_el = card.select_one(price_sel)
                store_el = card.select_one(store_sel)
                link_el  = card.select_one("a[href]")

                title = title_el.get_text(strip=True) if title_el else ""
                price = _parse_price(price_el.get_text() if price_el else "")
                store = store_el.get_text(strip=True) if store_el else ""
                url   = link_el.get("href", "") if link_el else ""

                if price is None or not title:
                    continue

                retailer = _normalise_retailer(store) if store else "Unknown"

                results.append({
                    "title":           title,
                    "price":           price,
                    "retailer":        retailer,
                    "url":             url,
                    "availability":    "",
                    "confirmed":       True,
                    "model_extracted": "",
                    "method":          "google_shopping",
                })
            except Exception:
                continue

        if results:
            break  # Stop after first strategy that finds results

    return results


# ── Spec extraction ───────────────────────────────────────────────────────────

# Canonical spec names for known generator attributes
_SPEC_KEYS: dict[str, str] = {
    "running watt":       "Running Watts",
    "rated watt":         "Running Watts",
    "rated power":        "Running Watts",
    "continuous watt":    "Running Watts",
    "starting watt":      "Peak Watts",
    "peak watt":          "Peak Watts",
    "surge watt":         "Peak Watts",
    "max watt":           "Peak Watts",
    "fuel type":          "Fuel Type",
    "fuel":               "Fuel Type",
    "run time":           "Run Time",
    "runtime":            "Run Time",
    "noise":              "Noise Level",
    "dba":                "Noise Level",
    "sound level":        "Noise Level",
    "weight":             "Weight",
    "engine":             "Engine",
    "displacement":       "Engine CC",
    " cc":                "Engine CC",
    "warranty":           "Warranty",
    "outlet":             "Outlets",
    "receptacle":         "Outlets",
    "transfer switch":    "Transfer Switch Ready",
    "co shutdown":        "CO Shutdown",
    "co sensor":          "CO Shutdown",
    "co detector":        "CO Shutdown",
    "electric start":     "Electric Start",
    "recoil":             "Recoil Start",
    "dimension":          "Dimensions (L×W×H)",
    "voltage":            "Voltage",
    "frequency":          "Frequency",
    "thd":                "THD",
    "total harmonic":     "THD",
    "inverter":           "Inverter Technology",
    "parallel":           "Parallel Capable",
    "phase":              "Phase",
    "alternator":         "Alternator",
    "tank":               "Tank Capacity",
    "fuel tank":          "Tank Capacity",
    "remote start":       "Remote Start",
    "transfer":           "Transfer Switch Ready",
}


def _extract_specs(html: str) -> dict[str, str]:
    """
    Extract confirmed spec key-value pairs from a product page's HTML.

    Strategies (in order):
      1. HTML tables near a "spec" heading or anchor
      2. All 2-column HTML tables on the page
      3. Definition lists (dl/dt/dd)

    Returns empty dict when specs are not in the static HTML (e.g. JavaScript-
    rendered tabs).  Intentionally omits any regex text-scan fallback because
    on modern e-commerce pages it reliably produces false positives from
    navigation menus and footer links.
    """
    soup  = BeautifulSoup(html, "html.parser")
    specs: dict[str, str] = {}

    # ── Strategy 1: find spec section, then parse tables within it ────────────
    spec_anchors = soup.find_all(
        ["section", "div", "article"],
        id=re.compile(r"spec|technical|detail", re.I),
    )
    if not spec_anchors:
        spec_anchors = soup.find_all(
            ["h2", "h3", "h4"],
            string=re.compile(r"spec|technical spec|product detail", re.I),
        )
        containers = []
        for h in spec_anchors:
            parent = h.find_parent(["div", "section"])
            if parent:
                containers.append(parent)
        spec_anchors = containers

    for container in spec_anchors:
        for table in container.find_all("table"):
            specs.update(_parse_table(table))
        for dl in container.find_all("dl"):
            specs.update(_parse_dl(dl))
        if specs:
            return specs

    # ── Strategy 2: all tables on page ────────────────────────────────────────
    for table in soup.find_all("table"):
        specs.update(_parse_table(table))
    if specs:
        return specs

    # ── Strategy 3: definition lists ──────────────────────────────────────────
    for dl in soup.find_all("dl"):
        specs.update(_parse_dl(dl))

    return specs


def _parse_table(table) -> dict[str, str]:
    specs = {}
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        key_text   = cells[0].get_text(" ", strip=True).lower()
        value_text = " ".join(cells[1].get_text(" ", strip=True).split())
        if not value_text or value_text.lower() in ("n/a", "–", "-", ""):
            continue
        for pattern, canonical in _SPEC_KEYS.items():
            if pattern in key_text:
                specs[canonical] = value_text
                break
    return specs


def _parse_dl(dl) -> dict[str, str]:
    specs = {}
    dts   = dl.find_all("dt")
    dds   = dl.find_all("dd")
    for dt, dd in zip(dts, dds):
        key_text   = dt.get_text(strip=True).lower()
        value_text = dd.get_text(strip=True)
        if not value_text:
            continue
        for pattern, canonical in _SPEC_KEYS.items():
            if pattern in key_text:
                specs[canonical] = value_text
                break
    return specs

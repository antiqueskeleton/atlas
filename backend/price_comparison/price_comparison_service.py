"""
Orchestrates competitive shopping data collection.

Data hierarchy per brand:
  Primary brand (with explicit model):
    1. Shopify JSON → MSRP + sale price directly from manufacturer
    2. Google Shopping → retailer prices (filtered, no regex noise)
    3. Manufacturer page HTML → confirmed specs
  Comparison brands (v2, spec-matched):
    1. AI comparable matching → the active provider names each brand's
       closest model to the primary product's key attributes (wattage/
       fuel/start/type) — the AI supplies only the model NAME; every
       displayed number still comes from the scrape pipeline below
    2. Shopify JSON → MSRP for the matched model
    3. Manufacturer page HTML → specs for the matched model
    Legacy fallback (no provider, or matching failed): Google Shopping
    top-result title → extract model number, as before.
"""
from __future__ import annotations

from backend.price_comparison.comparable_finder import (
    extract_key_attrs,
    find_comparable_models,
)
from backend.price_comparison.price_comparison_repository import PriceComparisonRepository
from backend.price_comparison import google_shopping_scraper as scraper


class PriceComparisonService:

    def __init__(self):
        self.repo = PriceComparisonRepository()
        self.repo.initialize()

    # ── Public ─────────────────────────────────────────────────────────────────

    def run_comparison(
        self,
        primary_brand: str,
        primary_model: str,
        comp_brands: list[str],
        keywords: str = "generator",
        retailer_urls: list[str] | None = None,
        progress_callback=None,
        key_attrs: dict | None = None,
        provider=None,
    ) -> dict:
        """
        Collect current pricing and specs for the primary product and all
        comparison brands.  Saves a price snapshot to the DB after each fetch
        so history accumulates over repeated runs.

        key_attrs — optional user overrides for the 4 key comparison
        attributes (watts/fuel_type/start_type/generator_type); non-blank
        values win over what the primary's spec scrape found.
        provider — the active AI provider; when present, comparison models
        are spec-matched to the primary via one comparable-matching call
        instead of "whatever tops Google Shopping" (v2). None keeps the
        legacy search path.

        Returns:
        {
          "brands": [
            {
              "brand":          str,
              "model":          str,      # entered model or matched/extracted model
              "model_resolved": str,      # "" for primary; matched/extracted for comps
              "model_source":   "user" | "ai_match" | "search",
              "key_specs":      {watts, fuel_type, start_type, generator_type},
              "search_q":       str,
              "prices": [
                {retailer, title, price, url, prev_price, change_pct, method}
              ],
              "specs":    {spec_name: value},  # confirmed only
              "spec_src": str,            # URL specs came from
              "status":   "ok" | "no_prices" | "error",
              "rating":       float | None,   # opportunistic, from best-price URL
              "review_count": int | None,
            },
            ...
          ],
          "match_note": str,   # why AI matching was skipped/failed, "" if fine
        }
        """
        output = []
        total  = 1 + len(comp_brands)

        # ── Primary brand ──────────────────────────────────────────────────────
        if progress_callback:
            progress_callback(primary_brand, 1, total)

        primary_entry = self._fetch_primary(
            primary_brand, primary_model, keywords,
            retailer_urls=retailer_urls or [],
        )
        primary_entry["model_source"] = "user"

        # Key attributes: what the spec scrape confirmed, with any non-blank
        # user overrides winning — these drive the comparable matching.
        primary_title = (primary_entry["prices"][0].get("title", "")
                         if primary_entry["prices"] else "")
        attrs = extract_key_attrs(primary_entry["specs"], title=primary_title)
        for key, value in (key_attrs or {}).items():
            if str(value).strip():
                attrs[key] = str(value).strip()
        primary_entry["key_specs"] = attrs
        output.append(primary_entry)

        # ── Comparable matching (v2) — one call names every brand's model ─────
        matches: dict[str, str] = {}
        match_note = ""
        if comp_brands:
            if provider is not None:
                if progress_callback:
                    progress_callback("Matching comparable models (AI)", 1, total)
                matches, match_note = find_comparable_models(
                    provider,
                    {"brand": primary_brand, "model": primary_model, **attrs},
                    comp_brands,
                )
            else:
                match_note = ("No AI provider configured — using each brand's "
                              "top search result instead of a spec-matched model.")

        # ── Comparison brands ──────────────────────────────────────────────────
        for idx, brand in enumerate(comp_brands):
            if progress_callback:
                progress_callback(brand, idx + 2, total)

            entry = self._fetch_comp(brand, keywords,
                                     resolved_model=matches.get(brand, ""))
            output.append(entry)

        return {"brands": output, "match_note": match_note}

    def get_price_history(self, brand: str, model: str,
                          retailer: str) -> list[dict]:
        return self.repo.get_price_history(brand, model or brand, retailer)

    def clear_specs(self, brand: str, model: str):
        """Force a fresh spec scrape on the next run."""
        self.repo.clear_specs(brand, model)

    # ── Primary brand (explicit model entered by user) ─────────────────────────

    def _fetch_primary(self, brand: str, model: str, keywords: str,
                       retailer_urls: list[str] | None = None) -> dict:
        entry: dict = {
            "brand":          brand,
            "model":          model,
            "model_resolved": "",
            "search_q":       f"{brand} {model}".strip(),
            "prices":         [],
            "specs":          {},
            "spec_src":       "",
            "status":         "ok",
        }

        try:
            prices: list[dict] = []

            # ── Tier 1: Shopify JSON — most reliable, gives MSRP ──────────────
            if model.strip():
                shopify = scraper.fetch_shopify_product(brand, model)
                if shopify and shopify.get("sale_price"):
                    prices.append({
                        "retailer":    "Manufacturer (MSRP)",
                        "title":       shopify.get("title", f"{brand} {model}"),
                        "price":       shopify["sale_price"],
                        "url":         shopify.get("source_url", ""),
                        "availability": "",
                        "confirmed":   True,
                        "method":      "shopify_direct",
                    })

            # ── Tier 2: Google Shopping — retailer prices ──────────────────────
            gshop_prices = scraper.search_product(brand, model, keywords)
            prices.extend(gshop_prices)

            # ── Tier 3: User-supplied retailer product page URLs ───────────────
            for url in (retailer_urls or []):
                url = url.strip()
                if not url:
                    continue
                result = scraper.scrape_url_for_price(url)
                if result:
                    # Avoid duplicate retailer entries
                    existing_retailers = {p["retailer"] for p in prices}
                    if result["retailer"] not in existing_retailers:
                        prices.append(result)

            if prices:
                db_model = model or brand
                self.repo.save_snapshots(brand, db_model, entry["search_q"], prices)
                for p in prices:
                    prev = self.repo.get_previous_price(brand, db_model, p["retailer"])
                    p["prev_price"] = prev
                    p["change_pct"] = (
                        round((p["price"] - prev) / prev * 100, 1)
                        if prev and prev > 0 else None
                    )
                entry["prices"] = prices
            else:
                entry["status"] = "no_prices"

            # ── Tier 3: Specs — manufacturer page first, then Google ───────────
            if model.strip():
                cached = self.repo.get_specs(brand, model)
                if cached:
                    entry["specs"]    = cached
                    entry["spec_src"] = "(cached)"
                else:
                    spec_dict, src = scraper.scrape_manufacturer_specs(brand, model)
                    if spec_dict:
                        self.repo.save_specs(brand, model, spec_dict, src)
                    entry["specs"]    = spec_dict
                    entry["spec_src"] = src

        except Exception as exc:
            entry["status"] = f"error: {exc}"

        self._attach_rating(entry)
        return entry

    # ── Comparison brand (model matched by AI, or discovered by search) ───────

    def _fetch_comp(self, brand: str, keywords: str,
                    resolved_model: str = "") -> dict:
        """
        resolved_model — a spec-matched model name from comparable_finder
        (v2). When present, discovery is skipped and prices/specs are
        fetched for THAT model; empty falls back to the legacy top-search-
        result path so a failed/skipped AI match never aborts the brand.
        """
        entry: dict = {
            "brand":          brand,
            "model":          "",
            "model_resolved": "",
            "model_source":   "ai_match" if resolved_model else "search",
            "search_q":       (f"{brand} {resolved_model}".strip() if resolved_model
                               else f"{brand} {keywords}".strip()),
            "prices":         [],
            "specs":          {},
            "spec_src":       "",
            "status":         "ok",
        }

        try:
            prices: list[dict] = []

            if resolved_model:
                # ── v2: targeted Google Shopping search for the matched model ──
                prices.extend(scraper.search_product(brand, resolved_model, keywords))
                entry["model_resolved"] = resolved_model
            else:
                # ── Legacy: find top result, extract model from its title ──────
                gshop_results = scraper.search_for_models(brand, keywords, max_results=5)
                if gshop_results:
                    for r in gshop_results:
                        if r.get("model_extracted"):
                            resolved_model = r["model_extracted"]
                            break
                    # Include all Google Shopping prices regardless
                    prices.extend(gshop_results)
                    entry["model_resolved"] = resolved_model

            # ── Tier 2: Shopify JSON for the extracted model ───────────────────
            if resolved_model:
                shopify = scraper.fetch_shopify_product(brand, resolved_model)
                if shopify and shopify.get("sale_price"):
                    prices.insert(0, {
                        "retailer":    "Manufacturer (MSRP)",
                        "title":       shopify.get("title", f"{brand} {resolved_model}"),
                        "price":       shopify["sale_price"],
                        "url":         shopify.get("source_url", ""),
                        "availability": "",
                        "confirmed":   True,
                        "method":      "shopify_direct",
                    })

            if prices:
                db_model = resolved_model or brand
                self.repo.save_snapshots(brand, db_model, entry["search_q"], prices)
                for p in prices:
                    prev = self.repo.get_previous_price(brand, db_model, p["retailer"])
                    p["prev_price"] = prev
                    p["change_pct"] = (
                        round((p["price"] - prev) / prev * 100, 1)
                        if prev and prev > 0 else None
                    )
                entry["prices"] = prices
            else:
                entry["status"] = "no_prices"
            # The model label stays even when no prices came back — an
            # AI-matched model with specs but no live listings should still
            # show WHICH model was compared, not a blank.
            entry["model"] = resolved_model

            # ── Tier 3: Specs for extracted model ─────────────────────────────
            if resolved_model:
                cached = self.repo.get_specs(brand, resolved_model)
                if cached:
                    entry["specs"]    = cached
                    entry["spec_src"] = "(cached)"
                else:
                    spec_dict, src = scraper.scrape_manufacturer_specs(brand, resolved_model)
                    if spec_dict:
                        self.repo.save_specs(brand, resolved_model, spec_dict, src)
                    entry["specs"]    = spec_dict
                    entry["spec_src"] = src

        except Exception as exc:
            entry["status"] = f"error: {exc}"

        title = entry["prices"][0].get("title", "") if entry["prices"] else ""
        entry["key_specs"] = extract_key_attrs(entry["specs"], title=title)
        self._attach_rating(entry)
        return entry

    # ── Opportunistic customer rating ─────────────────────────────────────────

    @staticmethod
    def _attach_rating(entry: dict):
        """
        Amazon-compare-style Customer Rating row, fetched from the entry's
        best-priced retailer listing via the Targeted Review retail scraper
        (JSON-LD aggregateRating). Strictly opportunistic — Amazon CAPTCHAs
        and blocked retailers are common, so ANY failure degrades to None
        and must never fail a brand whose price fetch worked.
        """
        entry.setdefault("rating", None)
        entry.setdefault("review_count", None)
        candidates = sorted(
            (p for p in entry.get("prices", [])
             if p.get("url") and p.get("method") != "shopify_direct"
             and isinstance(p.get("price"), (int, float))),
            key=lambda p: p["price"],
        )
        if not candidates:
            return
        try:
            from backend.targeted_review.retailer_provider import RetailerListingProvider
            listing = RetailerListingProvider().fetch_listing(candidates[0]["url"])
            if not listing.get("error"):
                entry["rating"] = listing.get("rating")
                entry["review_count"] = listing.get("review_count")
        except Exception:
            pass

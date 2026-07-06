"""
Orchestrates competitive shopping data collection.

Data hierarchy per brand:
  Primary brand (with explicit model):
    1. Shopify JSON → MSRP + sale price directly from manufacturer
    2. Google Shopping → retailer prices (filtered, no regex noise)
    3. Manufacturer page HTML → confirmed specs
  Comparison brands (model not known in advance):
    1. Google Shopping → discover top-result title → extract model number
    2. Shopify JSON → MSRP for extracted model
    3. Manufacturer page HTML → specs for extracted model
"""
from __future__ import annotations

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
    ) -> dict:
        """
        Collect current pricing and specs for the primary product and all
        comparison brands.  Saves a price snapshot to the DB after each fetch
        so history accumulates over repeated runs.

        Returns:
        {
          "brands": [
            {
              "brand":          str,
              "model":          str,      # entered model or extracted model
              "model_resolved": str,      # "" for primary; extracted for comp brands
              "search_q":       str,
              "prices": [
                {retailer, title, price, url, prev_price, change_pct, method}
              ],
              "specs":    {spec_name: value},  # confirmed only
              "spec_src": str,            # URL specs came from
              "status":   "ok" | "no_prices" | "error",
            },
            ...
          ]
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
        output.append(primary_entry)

        # ── Comparison brands ──────────────────────────────────────────────────
        for idx, brand in enumerate(comp_brands):
            if progress_callback:
                progress_callback(brand, idx + 2, total)

            entry = self._fetch_comp(brand, keywords)
            output.append(entry)

        return {"brands": output}

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

        return entry

    # ── Comparison brand (model discovered automatically) ─────────────────────

    def _fetch_comp(self, brand: str, keywords: str) -> dict:
        entry: dict = {
            "brand":          brand,
            "model":          "",
            "model_resolved": "",
            "search_q":       f"{brand} {keywords}".strip(),
            "prices":         [],
            "specs":          {},
            "spec_src":       "",
            "status":         "ok",
        }

        try:
            # ── Tier 1: Google Shopping — find top result, extract model ───────
            gshop_results = scraper.search_for_models(brand, keywords, max_results=5)

            resolved_model = ""
            prices: list[dict] = []

            if gshop_results:
                # Use the first result that has a model number extracted
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
                entry["model"]  = resolved_model
            else:
                entry["status"] = "no_prices"

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

        return entry

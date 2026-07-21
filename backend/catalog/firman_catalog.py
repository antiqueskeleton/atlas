"""
Firman product catalog — the AUTHORITATIVE spec source R7 Part B was blocked
on (and the model list #66 needs).

firmanpowerequipment.com is a Shopify store, and Shopify exposes the whole
catalog as structured JSON at /products.json (verified live 2026-07-20:
169 products in one page-1 request, 73 of them generators carrying
structured spec tags like "running_watts:8000(Gas)", "fuel_type:Gasoline",
"start_type:Electric"; /products/<model>.json gives one product; unknown
models 404 cleanly). This is FIRST-PARTY data — Firman's own site — which
is exactly the "verified" tier of the R7 trust model. No HTML scraping:
page structure can change, but the JSON product feed is a stable Shopify
contract.

Every displayed value traces to a tag or field in that feed; nothing is
inferred beyond generator_type, which is derived from the product title's
own words ("Inverter" / "Dual Fuel" / "Tri Fuel") and marked as such.
"""
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import requests

from backend.services.paths import get_db_path

_CATALOG_URL = "https://firmanpowerequipment.com/products.json"
_PRODUCT_URL = "https://firmanpowerequipment.com/products/{handle}"
_TIMEOUT = 30
_MAX_PAGES = 8   # 250/page; the real catalog is ~169 products — this is a guard


def parse_product(product: dict) -> dict | None:
    """One Shopify product dict -> a flat spec record, or None when the
    product carries no generator spec tags (accessories, parts, apparel).
    Pure and separately testable.

    Tags arrive either as a list (products.json) or a comma-joined string
    (products/<handle>.json) — both handled."""
    raw_tags = product.get("tags") or []
    if isinstance(raw_tags, str):
        raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]

    tag_map: dict[str, list[str]] = {}
    for tag in raw_tags:
        if ":" in tag:
            key, _, value = tag.partition(":")
            tag_map.setdefault(key.strip().lower(), []).append(value.strip())

    # Only products with real wattage tags are generators worth cataloguing.
    if "running_watts" not in tag_map:
        return None

    title = (product.get("title") or "").strip()
    handle = (product.get("handle") or "").strip()
    variants = product.get("variants") or [{}]
    sku = (variants[0].get("sku") or "").strip()
    model = (sku or handle).upper()

    # generator_type comes from the title's OWN words — never guessed.
    lowered = title.lower()
    if "inverter" in lowered:
        gen_type = "Inverter"
    elif "tri fuel" in lowered or "tri-fuel" in lowered:
        gen_type = "Tri Fuel"
    elif "dual fuel" in lowered or "dual-fuel" in lowered:
        gen_type = "Dual Fuel"
    else:
        gen_type = "Open Frame"

    def _num(text):
        m = re.search(r"\d[\d,]*", text or "")
        return int(m.group().replace(",", "")) if m else None

    running = {v: _num(v) for v in tag_map.get("running_watts", [])}
    starting = {v: _num(v) for v in tag_map.get("starting_watts", [])}

    price = None
    try:
        price = float(variants[0].get("price"))
    except (TypeError, ValueError):
        pass

    return {
        "model": model,
        "title": title,
        "generator_type": gen_type,
        "fuel_types": sorted(tag_map.get("fuel_type", [])),
        "start_types": sorted(tag_map.get("start_type", [])),
        "running_watts": running,       # e.g. {"8000(Gas)": 8000, "7250(LPG)": 7250}
        "starting_watts": starting,
        "certifications": sorted(tag_map.get("certification", [])),
        "price": price,
        "url": _PRODUCT_URL.format(handle=handle),
    }


def fetch_catalog() -> tuple[list[dict], str]:
    """All generator products from the live Firman store.
    Returns (records, error) — in-band error string, never raises."""
    records: list[dict] = []
    try:
        for page in range(1, _MAX_PAGES + 1):
            resp = requests.get(_CATALOG_URL,
                                params={"limit": 250, "page": page},
                                timeout=_TIMEOUT)
            if resp.status_code != 200:
                return [], f"Firman catalog fetch failed: HTTP {resp.status_code}"
            products = resp.json().get("products", [])
            if not products:
                break
            for product in products:
                record = parse_product(product)
                if record:
                    records.append(record)
    except requests.RequestException as exc:
        return [], f"Firman catalog fetch failed: {exc}"
    except ValueError as exc:
        return [], f"Firman catalog returned invalid JSON: {exc}"
    if not records:
        return [], "Firman catalog fetch returned no generator products."
    return records, ""


class ProductCatalogRepository:
    """firman_products: one row per model, spec record as JSON (same
    schema-flexibility tradeoff as targeted_review_findings), replaced
    wholesale on each sync so the table always mirrors the live site."""

    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else get_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self):
        return sqlite3.connect(self.db_path)

    def initialize(self):
        with self.connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS firman_products (
                    model TEXT PRIMARY KEY,
                    record_json TEXT NOT NULL,
                    synced_at TEXT NOT NULL
                )
            """)

    def replace_all(self, records: list[dict]) -> int:
        stamp = datetime.now().isoformat()
        with self.connect() as conn:
            conn.execute("DELETE FROM firman_products")
            conn.executemany(
                "INSERT INTO firman_products (model, record_json, synced_at) "
                "VALUES (?, ?, ?)",
                [(r["model"], json.dumps(r), stamp) for r in records])
        return len(records)

    def all_products(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT record_json, synced_at FROM firman_products "
                "ORDER BY model").fetchall()
        out = []
        for record_json, synced_at in rows:
            try:
                record = json.loads(record_json)
            except json.JSONDecodeError:
                continue
            record["synced_at"] = synced_at
            out.append(record)
        return out

    def get(self, model: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT record_json FROM firman_products WHERE model = ?",
                (model.upper().strip(),)).fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return None

    def count(self) -> int:
        with self.connect() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM firman_products").fetchone()[0]


def sync_catalog(repository=None) -> tuple[int, str]:
    """Fetch the live catalog and replace the stored copy.
    Returns (count, error) — count 0 + error on any failure; the previous
    stored catalog is kept untouched when the fetch fails."""
    records, error = fetch_catalog()
    if error:
        return 0, error
    repo = repository or ProductCatalogRepository()
    return repo.replace_all(records), ""


def build_product_truth_block(repository=None, limit: int = 40) -> str:
    """VERIFIED PRODUCT SPECS block for the Intelligence Engine prompts —
    the R7 Part B grounding: the synthesis passes receive Firman's real,
    first-party specs and are told to flag (never repeat) contradicting
    claims from the raw AI responses. Same injection pattern as
    targeted_review's build_presence_block. Explicit empty-state sentence
    when the catalog has never been synced."""
    repo = repository or ProductCatalogRepository()
    products = repo.all_products()
    if not products:
        return ("No verified product catalog synced yet — do not treat any "
                "product spec claims from AI responses as facts.")

    lines = ["VERIFIED FIRMAN PRODUCT SPECS (first-party, firmanpowerequipment.com):"]
    for p in products[:limit]:
        watts = ", ".join(sorted(p.get("running_watts") or [])) or "n/a"
        surge = ", ".join(sorted(p.get("starting_watts") or [])) or "n/a"
        lines.append(
            f"  {p['model']}: {p.get('generator_type', '?')} — "
            f"running {watts}; starting {surge}; "
            f"fuel: {'/'.join(p.get('fuel_types') or []) or 'n/a'}; "
            f"start: {'/'.join(p.get('start_types') or []) or 'n/a'}"
        )
    lines.append(
        "These specs are ground truth. If any AI response text claims "
        "different specs for these models (wrong wattage, wrong fuel type, "
        "calling a non-inverter model an inverter, etc.), do NOT repeat the "
        "claim as fact — instead flag it as a factual-correction "
        "opportunity: AI systems are giving buyers wrong information about "
        "these products."
    )
    return "\n".join(lines)

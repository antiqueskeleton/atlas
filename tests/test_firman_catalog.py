"""
Firman product catalog (R7 Part B's verified spec source): parse_product is
pure and exercised against the real Shopify shapes (verified live
2026-07-20); fetch paths use mocked requests; repository against tmp-path.
"""
from unittest.mock import MagicMock, patch

from backend.catalog.firman_catalog import (
    ProductCatalogRepository, build_product_truth_block, fetch_catalog,
    parse_product, sync_catalog,
)

# The real H08051 shape (products.json: tags as a LIST) — condensed from the
# live feed. Title says Dual Fuel; the tags carry the structured specs.
_H08051 = {
    "title": "Dual Fuel Portable Generator 8000W Electric Start 120/240V",
    "handle": "h08051",
    "variants": [{"sku": "H08051", "price": "1399.99"}],
    "tags": ["certification:cETL", "certification:EPA",
             "fuel_type:Gasoline", "fuel_type:Liquified Petroleum Gas",
             "running_watts:8000(Gas)", "running_watts:7250(LPG)",
             "starting_watts:10000(Gas)", "starting_watts:9050(LPG)",
             "start_type:Electric", "start_type:Recoil"],
}


def test_parse_product_extracts_structured_specs():
    p = parse_product(_H08051)
    assert p["model"] == "H08051"
    assert p["generator_type"] == "Dual Fuel"        # from the title's own words
    assert p["fuel_types"] == ["Gasoline", "Liquified Petroleum Gas"]
    assert p["start_types"] == ["Electric", "Recoil"]
    assert p["running_watts"]["8000(Gas)"] == 8000
    assert p["starting_watts"]["10000(Gas)"] == 10000
    assert p["price"] == 1399.99
    assert p["url"].endswith("/products/h08051")


def test_parse_product_accepts_comma_string_tags():
    """products/<handle>.json returns tags as one comma-joined string."""
    prod = dict(_H08051, tags=", ".join(_H08051["tags"]))
    p = parse_product(prod)
    assert p["model"] == "H08051"
    assert p["running_watts"]["7250(LPG)"] == 7250


def test_parse_product_inverter_and_open_frame_types():
    inv = dict(_H08051, title="Inverter Portable Generator 3300W Quiet")
    assert parse_product(inv)["generator_type"] == "Inverter"
    plain = dict(_H08051, title="Gas Portable Generator 4450W Recoil Start")
    assert parse_product(plain)["generator_type"] == "Open Frame"


def test_parse_product_non_generator_returns_none():
    """Accessories/parts carry no running_watts tag and must be skipped."""
    cover = {"title": "Generator Cover Large", "handle": "cover-l",
             "variants": [{"sku": "1001"}], "tags": ["Webstore:Marketing"]}
    assert parse_product(cover) is None


def test_fetch_catalog_paginates_and_reports_errors_in_band():
    page1 = MagicMock(status_code=200)
    page1.json.return_value = {"products": [_H08051]}
    page2 = MagicMock(status_code=200)
    page2.json.return_value = {"products": []}
    with patch("backend.catalog.firman_catalog.requests.get",
               side_effect=[page1, page2]):
        records, error = fetch_catalog()
    assert error == "" and len(records) == 1

    bad = MagicMock(status_code=503)
    with patch("backend.catalog.firman_catalog.requests.get", return_value=bad):
        records, error = fetch_catalog()
    assert records == [] and "503" in error


def test_repository_roundtrip_and_case_insensitive_get(tmp_path):
    repo = ProductCatalogRepository(db_path=tmp_path / "c.db")
    assert repo.count() == 0
    repo.replace_all([parse_product(_H08051)])
    assert repo.count() == 1
    assert repo.get("h08051")["generator_type"] == "Dual Fuel"
    assert repo.get("NOPE") is None
    got = repo.all_products()
    assert got[0]["model"] == "H08051" and got[0]["synced_at"]


def test_sync_failure_keeps_previous_catalog(tmp_path):
    repo = ProductCatalogRepository(db_path=tmp_path / "c.db")
    repo.replace_all([parse_product(_H08051)])
    bad = MagicMock(status_code=500)
    with patch("backend.catalog.firman_catalog.requests.get", return_value=bad):
        count, error = sync_catalog(repo)
    assert count == 0 and error
    assert repo.count() == 1              # stored copy untouched


def test_truth_block_grounds_the_h08051_hallucination(tmp_path):
    """The exact R7B scenario: AI called the H08051 a 'quiet inverter'. The
    truth block must state the first-party type (Dual Fuel) and instruct the
    synthesis to flag, not repeat, contradicting claims."""
    repo = ProductCatalogRepository(db_path=tmp_path / "c.db")
    repo.replace_all([parse_product(_H08051)])
    block = build_product_truth_block(repo)
    assert "H08051" in block and "Dual Fuel" in block
    assert "8000(Gas)" in block
    assert "do NOT repeat" in block
    assert "factual-correction" in block


def test_truth_block_empty_state_is_explicit(tmp_path):
    repo = ProductCatalogRepository(db_path=tmp_path / "c.db")
    block = build_product_truth_block(repo)
    assert "No verified product catalog synced yet" in block
    assert "do not treat" in block.lower()

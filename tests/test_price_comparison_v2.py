"""
Price Comparison v2 (spec-matched comparables) — comparable_finder parsing/
attribute extraction against canned LLM responses, service wiring with
mocked scraper + provider (never live HTTP), and the Amazon-style spec-row
ordering helper.
"""
from unittest.mock import MagicMock, patch

from backend.price_comparison.comparable_finder import (
    extract_key_attrs,
    find_comparable_models,
    parse_comparable_models,
)
from backend.price_comparison.price_comparison_service import PriceComparisonService
from desktop.pages.price_comparison_page import _ordered_spec_rows


# ── parse_comparable_models ───────────────────────────────────────────────────

def test_parse_comparable_models_clean_json():
    text = '[{"brand": "Champion", "model": "100111"}, {"brand": "Westinghouse", "model": "WGen9500DF"}]'
    assert parse_comparable_models(text) == {
        "Champion": "100111", "Westinghouse": "WGen9500DF"}


def test_parse_comparable_models_strips_code_fences_and_prose():
    text = ('Here are the matches:\n```json\n'
            '[{"brand": "DuroMax", "model": "XP13000EH"}]\n```\nHope that helps!')
    assert parse_comparable_models(text) == {"DuroMax": "XP13000EH"}


def test_parse_comparable_models_garbage_returns_empty():
    assert parse_comparable_models("I cannot help with that request.") == {}
    assert parse_comparable_models("") == {}
    assert parse_comparable_models('{"brand": "not-a-list"}') == {}


def test_parse_comparable_models_skips_malformed_items():
    text = '[{"brand": "Champion", "model": "100111"}, {"brand": ""}, "junk"]'
    assert parse_comparable_models(text) == {"Champion": "100111"}


# ── extract_key_attrs ─────────────────────────────────────────────────────────

def test_extract_key_attrs_from_canonical_spec_names():
    specs = {"Running Watts": "7500", "Starting Watts": "9500",
             "Fuel Type": "Gasoline/Propane", "Start Type": "Electric"}
    attrs = extract_key_attrs(specs, title="Firman T07571 Tri Fuel Generator")
    assert attrs["watts"] == "7500"          # running preferred over starting
    assert attrs["fuel_type"] == "Gasoline/Propane"
    assert attrs["start_type"] == "Electric"
    assert attrs["generator_type"] == "Portable"   # market default


def test_extract_key_attrs_detects_inverter_from_title():
    attrs = extract_key_attrs({}, title="Honda EU2200i Inverter Generator")
    assert attrs["generator_type"] == "Inverter"
    assert attrs["watts"] == ""              # missing stays blank, never guessed


# ── find_comparable_models ────────────────────────────────────────────────────

def _fake_provider(text, is_error=False):
    provider = MagicMock()
    provider.ask.return_value = MagicMock(is_error=is_error,
                                          executive_summary=text)
    return provider


def test_find_comparable_models_filters_to_requested_brands():
    provider = _fake_provider(
        '[{"brand": "champion", "model": "100111"},'
        ' {"brand": "Ryobi", "model": "RY907000"}]')
    matches, error = find_comparable_models(
        provider, {"brand": "Firman", "model": "T07571", "watts": "7500"},
        ["Champion", "Westinghouse"])
    # case-insensitive match returned under the caller's casing; the brand
    # never asked about (Ryobi) is dropped.
    assert matches == {"Champion": "100111"}
    assert error == ""
    assert "7500" in provider.ask.call_args[0][0]


def test_find_comparable_models_provider_error_is_in_band():
    provider = _fake_provider("no key configured", is_error=True)
    matches, error = find_comparable_models(
        provider, {"brand": "Firman", "model": "X"}, ["Champion"])
    assert matches == {}
    assert "failed" in error.lower()


def test_find_comparable_models_unparseable_response_is_in_band():
    provider = _fake_provider("Sorry, I can't produce JSON today.")
    matches, error = find_comparable_models(
        provider, {"brand": "Firman", "model": "X"}, ["Champion"])
    assert matches == {}
    assert "parseable" in error.lower()


def test_find_comparable_models_no_provider():
    matches, error = find_comparable_models(
        None, {"brand": "Firman", "model": "X"}, ["Champion"])
    assert matches == {}
    assert "provider" in error.lower()


# ── Service wiring ────────────────────────────────────────────────────────────

class _FakeRepo:
    def get_specs(self, brand, model):
        return {}

    def save_specs(self, *args):
        pass

    def save_snapshots(self, *args):
        pass

    def get_previous_price(self, *args):
        return None


def _service():
    svc = PriceComparisonService.__new__(PriceComparisonService)
    svc.repo = _FakeRepo()
    return svc


def _no_rating():
    return patch.object(PriceComparisonService, "_attach_rating",
                        lambda self, entry: entry.setdefault("rating", None)
                        or entry.setdefault("review_count", None))


def test_fetch_comp_with_resolved_model_skips_discovery():
    svc = _service()
    with patch("backend.price_comparison.price_comparison_service.scraper") as scr, \
         _no_rating():
        scr.search_product.return_value = [
            {"retailer": "Amazon", "title": "Champion 100111",
             "price": 899.0, "url": "u", "method": "google_shopping"}]
        scr.fetch_shopify_product.return_value = {}
        scr.scrape_manufacturer_specs.return_value = ({}, "")
        entry = svc._fetch_comp("Champion", "generator", resolved_model="100111")

    scr.search_for_models.assert_not_called()      # discovery skipped
    scr.search_product.assert_called_once()
    assert entry["model_source"] == "ai_match"
    assert entry["model_resolved"] == "100111"
    assert entry["model"] == "100111"


def test_fetch_comp_without_resolved_model_uses_legacy_search():
    svc = _service()
    with patch("backend.price_comparison.price_comparison_service.scraper") as scr, \
         _no_rating():
        scr.search_for_models.return_value = [
            {"retailer": "Amazon", "title": "Champion 201052 Generator",
             "price": 700.0, "url": "u", "model_extracted": "201052",
             "method": "google_shopping"}]
        scr.fetch_shopify_product.return_value = {}
        scr.scrape_manufacturer_specs.return_value = ({}, "")
        entry = svc._fetch_comp("Champion", "generator")

    scr.search_for_models.assert_called_once()
    assert entry["model_source"] == "search"
    assert entry["model_resolved"] == "201052"


def test_run_comparison_threads_ai_matches_and_falls_back_on_error():
    svc = _service()
    provider = _fake_provider('[{"brand": "Champion", "model": "100111"}]')

    with patch("backend.price_comparison.price_comparison_service.scraper") as scr, \
         _no_rating():
        scr.fetch_shopify_product.return_value = {}
        scr.search_product.return_value = []
        scr.search_for_models.return_value = []
        scr.scrape_manufacturer_specs.return_value = (
            {"Running Watts": "7500", "Fuel Type": "Gas", "Start Type": "Electric"},
            "https://spec")
        result = svc.run_comparison("Firman", "T07571",
                                    ["Champion", "Westinghouse"],
                                    provider=provider)

    primary, champ, westi = result["brands"]
    assert primary["model_source"] == "user"
    assert primary["key_specs"]["watts"] == "7500"
    assert champ["model_source"] == "ai_match"       # AI named a model
    assert champ["model_resolved"] == "100111"
    assert westi["model_source"] == "search"         # omitted by AI → legacy
    assert result["match_note"] == ""


def test_run_comparison_without_provider_notes_legacy_mode():
    svc = _service()
    with patch("backend.price_comparison.price_comparison_service.scraper") as scr, \
         _no_rating():
        scr.fetch_shopify_product.return_value = {}
        scr.search_product.return_value = []
        scr.search_for_models.return_value = []
        scr.scrape_manufacturer_specs.return_value = ({}, "")
        result = svc.run_comparison("Firman", "X", ["Champion"], provider=None)

    assert "No AI provider" in result["match_note"]
    assert result["brands"][1]["model_source"] == "search"


def test_run_comparison_key_attr_overrides_win():
    svc = _service()
    provider = _fake_provider('[]')  # parse yields {} → in-band note
    with patch("backend.price_comparison.price_comparison_service.scraper") as scr, \
         _no_rating():
        scr.fetch_shopify_product.return_value = {}
        scr.search_product.return_value = []
        scr.search_for_models.return_value = []
        scr.scrape_manufacturer_specs.return_value = (
            {"Running Watts": "7500"}, "https://spec")
        result = svc.run_comparison(
            "Firman", "X", ["Champion"], provider=provider,
            key_attrs={"watts": "9000", "fuel_type": "Tri Fuel",
                       "start_type": "", "generator_type": ""})

    key_specs = result["brands"][0]["key_specs"]
    assert key_specs["watts"] == "9000"          # override beats scraped 7500
    assert key_specs["fuel_type"] == "Tri Fuel"
    # blank overrides don't clobber detected values
    prompt = provider.ask.call_args[0][0]
    assert "9000" in prompt and "Tri Fuel" in prompt


# ── SerpApi shopping + title-derived key attributes ───────────────────────────

def test_serpapi_shopping_search_maps_results_to_price_dicts():
    from backend.price_comparison.google_shopping_scraper import serpapi_shopping_search
    payload = {"shopping_results": [
        {"title": "Firman 7500W Tri Fuel Portable Generator T07571",
         "extracted_price": 949.0, "source": "Lowe's",
         "product_link": "https://google.com/shopping/p/1"},
        {"title": "Firman cover accessory", "extracted_price": 29.99,
         "source": "Amazon", "link": "https://amazon.com/x"},   # < $50 filtered
        {"title": "No price item", "source": "Walmart"},         # no price filtered
    ]}
    with patch("backend.price_comparison.google_shopping_scraper.requests.get") as g:
        g.return_value = MagicMock(status_code=200, json=lambda: payload)
        results = serpapi_shopping_search("Firman", "Firman T07571 generator", "key123")
    assert len(results) == 1
    r = results[0]
    assert r["retailer"] == "Lowe's" and r["price"] == 949.0
    assert r["model_extracted"] == "T07571"
    assert r["method"] == "google_shopping" and r["confirmed"] is True


def test_serpapi_shopping_search_failures_are_in_band_empty():
    from backend.price_comparison.google_shopping_scraper import serpapi_shopping_search
    assert serpapi_shopping_search("Firman", "q", "") == []          # no key
    from requests import RequestException
    with patch("backend.price_comparison.google_shopping_scraper.requests.get",
               side_effect=RequestException("timeout")):
        assert serpapi_shopping_search("Firman", "q", "key") == []


def test_search_product_uses_serpapi_when_key_present():
    from backend.price_comparison import google_shopping_scraper as gss
    with patch.object(gss, "serpapi_shopping_search",
                      return_value=[{"title": "T", "price": 500.0,
                                     "retailer": "Walmart", "url": "u",
                                     "model_extracted": "", "method": "google_shopping",
                                     "availability": "", "confirmed": True}]) as s, \
         patch.object(gss, "_get") as legacy_get:
        results = gss.search_product("Firman", "T07571", "generator",
                                     serpapi_key="key123")
    s.assert_called_once()
    legacy_get.assert_not_called()      # no legacy HTML attempt when keyed
    assert results[0]["retailer"] == "Walmart"


def test_extract_key_attrs_from_titles():
    """Real v1.0 test finding: manufacturer pages often have NO spec markup
    (Firman's included) — retail listing titles are the confirmed fallback."""
    from backend.price_comparison.comparable_finder import (
        extract_key_attrs_from_titles, merge_key_attrs)
    titles = [
        "FIRMAN Tri Fuel 7,500-Watt Portable Generator Electric Start",
        "Firman T07571 Generator with remote start",
    ]
    attrs = extract_key_attrs_from_titles(titles)
    assert attrs["watts"] == "7500"
    assert attrs["fuel_type"] == "Tri Fuel"
    assert attrs["start_type"] == "Electric"          # first title wins
    assert attrs["generator_type"] == "Portable"

    # merge: scraped (non-blank) wins, titles fill blanks, never guessed
    merged = merge_key_attrs({"watts": "9500", "fuel_type": "", "start_type": "",
                              "generator_type": ""}, attrs)
    assert merged["watts"] == "9500"
    assert merged["fuel_type"] == "Tri Fuel"
    assert extract_key_attrs_from_titles([])["watts"] == ""


# ── Amazon-style spec-row ordering ────────────────────────────────────────────

def test_ordered_spec_rows_price_rating_key_attrs_then_rest():
    entries = [
        {"brand": "Firman", "model": "T07571",
         "prices": [{"retailer": "Amazon", "price": 999.0, "method": "g"},
                    {"retailer": "Walmart", "price": 949.0, "method": "g"}],
         "rating": 4.7, "review_count": 10902,
         "key_specs": {"watts": "7500", "fuel_type": "Tri Fuel",
                       "start_type": "Electric", "generator_type": "Portable"},
         "specs": {"Running Watts": "7500", "Starting Watts": "9500",
                   "Runtime": "12 hours"}},
        {"brand": "Champion", "model": "100111",
         "prices": [], "rating": None, "review_count": None,
         "key_specs": {"watts": "", "fuel_type": "", "start_type": "",
                       "generator_type": ""},
         "specs": {}},
    ]
    rows = _ordered_spec_rows(entries)
    labels = [label for label, _ in rows]

    assert labels[:6] == ["Best Price", "Customer Rating", "Wattage",
                          "Fuel Type", "Start Type", "Generator Type"]
    # Best price picks the LOWEST across retailers
    assert rows[0][1][0] == "$949.00 @ Walmart"
    assert rows[0][1][1] == "—"
    assert rows[1][1][0] == "4.7 ★ (10,902)"
    # Running Watts/Fuel Type suppressed (key rows cover them);
    # Starting Watts and Runtime kept.
    assert "Running Watts" not in labels
    assert "Starting Watts" in labels and "Runtime" in labels
    # Unconfirmed everything on the second entry renders as "—"
    assert rows[2][1][1] == "—"

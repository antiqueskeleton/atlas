"""
Spec-matched comparable-product discovery (Price Comparison v2).

The old comparison flow grabbed whatever model topped Google Shopping for
each brand — a 2000W inverter could end up "compared" against a 12,500W
dual-fuel unit. This module fixes the selection step: the active AI
provider is asked to name each brand's single closest comparable model,
matched on the four attributes that define generator comparability
(wattage class, fuel type, start type, generator type).

Factuality contract, same as the rest of Atlas: the AI supplies ONLY
candidate model names (stable, well-known catalog knowledge). Every
spec, price, and rating actually displayed comes from the existing
scrape/cache pipeline — an AI-suggested model whose specs can't be
confirmed shows "—" like any other unconfirmed value, never invented
numbers.
"""
import json
import re

# Canonical spec names produced by google_shopping_scraper's spec-name
# mapping — the keys extract_key_attrs() looks for, in priority order.
_WATTS_KEYS = ("Running Watts", "Rated Watts", "Wattage", "Starting Watts",
               "Peak Watts")
_FUEL_KEYS = ("Fuel Type", "Fuel")
_START_KEYS = ("Start Type", "Ignition System Type", "Ignition", "Starting System")

_COMPARE_PROMPT = (
    "The reference product is:\n"
    "Brand: {brand}\n"
    "Model: {model}\n"
    "{attr_lines}"
    "\n"
    "For each brand in this list, name that brand's single closest comparable "
    "generator model currently sold in the US market, matched on wattage "
    "class, fuel type, start type, and generator type: {brand_list}\n"
    "\n"
    "Return ONLY a valid JSON array with no other text, no markdown code "
    "fences, and no explanation. Use the manufacturer's model number, not a "
    "marketing name.\n"
    'Example: [{{"brand": "Champion", "model": "100111"}}, '
    '{{"brand": "Westinghouse", "model": "WGen9500DF"}}]\n'
    "If a brand has no comparable product, omit that brand from the array."
)


def parse_comparable_models(text: str) -> dict[str, str]:
    """
    {brand: model} from an LLM response — same defensive chain as
    brand_discovery._parse_brands (strip fences -> direct JSON -> first
    [...] block), giving up to {} rather than raising. Pure, so tests
    exercise real parsing against canned responses without a provider.
    """
    text = (text or "").strip()
    text = re.sub(r"```[a-z]*\n?", "", text).strip("` \n")

    def _from_list(items) -> dict[str, str]:
        result: dict[str, str] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            brand = str(item.get("brand", "")).strip()
            model = str(item.get("model", "")).strip()
            if brand and model:
                result[brand] = model
        return result

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return _from_list(data)
    except (json.JSONDecodeError, ValueError):
        pass

    m = re.search(r"\[.*\]", text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, list):
                return _from_list(data)
        except Exception:
            pass
    return {}


def extract_key_attrs(specs: dict, title: str = "") -> dict:
    """
    The 4 key comparison attributes from a confirmed-specs dict (canonical
    names from google_shopping_scraper's mapping). Generator type is rarely
    its own spec row, so it falls back to title keywords; "Portable" is the
    default the generator market itself assumes when nothing says otherwise.
    Missing attributes stay "" — never guessed.
    """
    def _first(keys):
        for key in keys:
            value = str(specs.get(key, "")).strip()
            if value:
                return value
        return ""

    text = f"{title} {' '.join(specs)} {' '.join(str(v) for v in specs.values())}".lower()
    if "inverter" in text:
        gen_type = "Inverter"
    elif "standby" in text:
        gen_type = "Standby"
    elif specs or title:
        gen_type = "Portable"
    else:
        gen_type = ""

    return {
        "watts": _first(_WATTS_KEYS),
        "fuel_type": _first(_FUEL_KEYS),
        "start_type": _first(_START_KEYS),
        "generator_type": gen_type,
    }


def extract_key_attrs_from_titles(titles: list[str]) -> dict:
    """
    The 4 key attributes derived from real retail LISTING TITLES
    ("Firman 7500W Tri Fuel Portable Generator Electric Start…") — the
    fallback when the manufacturer page yields no spec table, which real
    v1.0 testing showed is the COMMON case (Firman's own product page has
    no spec markup at all, just styled marketing blurbs). Titles come from
    confirmed shopping results, so this stays within the confirmed-data
    rule. First title that answers each attribute wins; unanswered
    attributes stay "" — never guessed.
    """
    attrs = {"watts": "", "fuel_type": "", "start_type": "", "generator_type": ""}
    for title in titles:
        t = " " + (title or "").lower() + " "
        if not attrs["watts"]:
            m = re.search(r"(\d{1,2}[,.]?\d{3})\s*(?:-?\s*watt|w\b)", t)
            if m:
                attrs["watts"] = m.group(1).replace(",", "").replace(".", "")
        if not attrs["fuel_type"]:
            if "tri fuel" in t or "tri-fuel" in t or "trifuel" in t:
                attrs["fuel_type"] = "Tri Fuel"
            elif "dual fuel" in t or "dual-fuel" in t:
                attrs["fuel_type"] = "Dual Fuel"
            elif "diesel" in t:
                attrs["fuel_type"] = "Diesel"
            elif "propane" in t:
                attrs["fuel_type"] = "Propane"
            elif "gasoline" in t or "gas powered" in t or "gas-powered" in t:
                attrs["fuel_type"] = "Gasoline"
        if not attrs["start_type"]:
            if "remote start" in t:
                attrs["start_type"] = "Remote + Electric"
            elif "electric start" in t or "electric-start" in t:
                attrs["start_type"] = "Electric"
            elif "recoil" in t:
                attrs["start_type"] = "Recoil"
        if not attrs["generator_type"]:
            if "inverter" in t:
                attrs["generator_type"] = "Inverter"
            elif "standby" in t:
                attrs["generator_type"] = "Standby"
            elif "generator" in t:
                attrs["generator_type"] = "Portable"
    return attrs


def merge_key_attrs(primary: dict, fallback: dict) -> dict:
    """Non-blank values from `primary` win; `fallback` fills the blanks."""
    return {
        key: (primary.get(key) or fallback.get(key) or "")
        for key in ("watts", "fuel_type", "start_type", "generator_type")
    }


def find_comparable_models(provider, primary: dict,
                           brands: list[str]) -> tuple[dict[str, str], str]:
    """
    One ask() to the active provider covering ALL comparison brands at once
    (a handful of brands fits one small JSON response — per-brand calls
    would multiply cost for no quality gain).

    primary: {"brand", "model", "watts", "fuel_type", "start_type",
              "generator_type"} — blank attributes are omitted from the
    prompt rather than sent as empty lines.

    Returns ({brand: model}, error) — in-band error string, never raises.
    """
    if provider is None:
        return {}, "No AI provider available for comparable matching."
    if not brands:
        return {}, ""

    attr_labels = [("watts", "Running watts"), ("fuel_type", "Fuel type"),
                   ("start_type", "Start type"), ("generator_type", "Generator type")]
    attr_lines = "".join(
        f"{label}: {primary[key]}\n"
        for key, label in attr_labels if primary.get(key)
    )
    prompt = _COMPARE_PROMPT.format(
        brand=primary.get("brand", ""),
        model=primary.get("model", ""),
        attr_lines=attr_lines,
        brand_list=", ".join(brands),
    )

    try:
        response = provider.ask(prompt)
    except Exception as exc:
        return {}, f"Comparable matching failed: {exc}"
    if getattr(response, "is_error", False):
        return {}, (f"Comparable matching failed: "
                    f"{response.executive_summary or 'provider error'}")

    matches = parse_comparable_models(response.executive_summary or "")
    if not matches:
        return {}, "AI response contained no parseable brand/model matches."

    # Only keep matches for brands actually asked about (case-insensitive),
    # returned under the caller's own casing.
    requested = {b.lower(): b for b in brands}
    filtered = {
        requested[brand.lower()]: model
        for brand, model in matches.items()
        if brand.lower() in requested
    }
    return filtered, ""

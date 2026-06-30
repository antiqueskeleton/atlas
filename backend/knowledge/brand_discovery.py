"""
Queries AI providers for a comprehensive generator brand list and returns
deduplicated names. Runs multiple providers in parallel when available.
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

_DISCOVERY_PROMPT = (
    "List every brand that manufactures portable generators, inverter generators, "
    "or home standby generators. Include only brand/manufacturer names — "
    "not model names, wattage types, product categories, or descriptions. "
    "Return ONLY a valid JSON array of strings with no other text, no markdown "
    "code fences, and no explanation.\n"
    'Example: ["Firman","Honda","Champion","Westinghouse","Generac","DuroMax"]'
)


def _parse_brands(text: str) -> list[str]:
    """Extract a list of brand name strings from an LLM response."""
    text = text.strip()
    # Strip markdown code fences
    text = re.sub(r"```[a-z]*\n?", "", text).strip("` \n")
    # Direct JSON parse
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return [str(b).strip() for b in result if str(b).strip()]
    except (json.JSONDecodeError, ValueError):
        pass
    # Find first [...] block
    m = re.search(r'\[(.+?)\]', text, re.DOTALL)
    if m:
        try:
            result = json.loads(f"[{m.group(1)}]")
            if isinstance(result, list):
                return [str(b).strip() for b in result if str(b).strip()]
        except Exception:
            pass
    # Last resort: pull quoted strings of reasonable brand-name length
    return [s for s in re.findall(r'"([^"]{2,50})"', text) if s.strip()]


def discover_brands(provider_manager, provider_names: list[str]) -> tuple[list[str], list[str]]:
    """
    Query each provider in parallel for a generator brand list.

    Returns:
        (brands_sorted, providers_queried)
        brands_sorted  — deduplicated, alphabetically sorted brand names
        providers_queried — names of providers that returned usable data
    """
    raw_results: list[str] = []
    providers_queried: list[str] = []
    lock = __import__("threading").Lock()

    def _query_one(name: str):
        try:
            provider = provider_manager.get_provider(name)
            response = provider.ask(_DISCOVERY_PROMPT)
            text = response.executive_summary or ""
            brands = _parse_brands(text)
            if brands:
                with lock:
                    raw_results.extend(brands)
                    providers_queried.append(name)
        except Exception:
            pass

    with ThreadPoolExecutor(max_workers=max(1, len(provider_names))) as pool:
        futures = [pool.submit(_query_one, n) for n in provider_names]
        for f in as_completed(futures):
            f.result()  # surface exceptions (already swallowed above)

    # Deduplicate case-insensitively, preserve first-seen casing
    seen: set[str] = set()
    deduped: list[str] = []
    for name in raw_results:
        key = name.lower().strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(name.strip())

    return sorted(deduped), providers_queried

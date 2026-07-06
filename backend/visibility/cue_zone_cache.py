"""
Shared per-response cue-zone caching for negation.py and recommendation.py.

Both modules' _cue_zones() functions are brand-independent — they only
depend on a sentence's own text, which never changes once a response is
saved. Without caching, summarize_responses() re-runs the exact same regex
work over the exact same old responses on every single call (every app
launch, every page refresh) — the dominant cost of analytics once the
brand-matching itself was fixed (see backend/visibility/brand_matcher.py).
Caching this once, permanently, converts the cost from O(all responses
ever collected) to O(responses collected since the cache was last built).

Format: a JSON object mapping sentence index (as a string key, since JSON
object keys must be strings) to that sentence's list of [start, end] zones.
Sentences with zero zones are omitted entirely (sparse) — every sentence in
the response is covered by this computation, so any index absent from the
dict is known to have zero zones, not "not yet computed."
"""
import json

from backend.visibility.clause_boundaries import SENTENCE_SPLIT


def compute_cue_zone_cache(response_text: str, cue_zones_fn) -> str:
    """
    cue_zones_fn: a _cue_zones(sent_lower: str) -> list[tuple[int,int]]
    function, e.g. negation._cue_zones or recommendation._cue_zones.
    """
    cache: dict[int, list[list[int]]] = {}
    for i, sentence in enumerate(SENTENCE_SPLIT.split(response_text)):
        zones = cue_zones_fn(sentence.lower())
        if zones:
            cache[i] = [list(z) for z in zones]
    return json.dumps(cache)


def parse_cue_zone_cache(cached_json: str | None) -> dict:
    """
    Parse a cached JSON string ONCE per response. detect_negative_brands/
    detect_recommended_brands loop per SENTENCE (often 20-40+ per response)
    — re-parsing the same JSON string on every sentence inside that loop
    would redo the same json.loads() dozens of times per response for no
    reason; parse once up front and look up from the resulting dict instead.
    """
    return json.loads(cached_json) if cached_json else {}


def zones_for_sentence(parsed_cache: dict, sentence_index: int) -> list[tuple[int, int]]:
    return [tuple(z) for z in parsed_cache.get(str(sentence_index), [])]

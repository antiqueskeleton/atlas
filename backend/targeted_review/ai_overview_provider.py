"""
Google AI Overviews presence via SerpApi (#97) — the single biggest
consumer AI surface Atlas couldn't see: the AI-generated answer block at
the top of Google results, which reaches more shoppers than every chat
assistant combined. No official API exists; SerpApi returns the parsed
ai_overview block with a normal search (free tier: 100 searches/month;
paid from ~$75/mo — key gated, nothing runs without one).

Design is COLLECTION-level, not per-brand: one search per canonical buying
query (5 queries per collection, regardless of how many brands are
checked), then every tracked brand is checked against each overview's text
with the core pipeline's word-boundary matching (#87). 100 free searches
= 20 full collections/month.
"""
import requests

from backend.targeted_review.base_platform_provider import PlatformProvider
from backend.visibility.brand_matcher import text_contains_term

_SEARCH_URL = "https://serpapi.com/search.json"
_TIMEOUT = 30

# The canonical AI-Overview-prone buying queries — the questions a real
# shopper asks Google where the AI Overview effectively IS the answer.
AI_OVERVIEW_QUERIES = [
    "best portable generator",
    "best portable generator for home backup",
    "best dual fuel generator",
    "quietest inverter generator",
    "most reliable generator brand",
]


class AIOverviewProvider(PlatformProvider):
    platform_name = "AI Overviews"
    credential_fields = {"api_key": "SerpApi Key"}

    def fetch_brand_presence(self, brand: str) -> dict:
        # Collection-level platform — the service calls fetch_all(brands)
        # so the 5 searches are shared across every brand instead of being
        # repeated per brand. Kept to satisfy the PlatformProvider contract.
        return {"brand": brand, "platform": self.platform_name,
                "error": "AI Overviews is collected for all brands at once — "
                         "use the Collect button."}

    def fetch_all(self, brands: list[str], progress_cb=None) -> list[dict]:
        """One finding per brand from the shared 5-query sweep."""
        api_key = self.credentials.get("api_key", "")
        if not api_key:
            error = ("No SerpApi key configured — add one in Settings "
                     "(serpapi.com, free tier: 100 searches/month).")
            return [{"brand": b, "platform": self.platform_name, "error": error}
                    for b in brands]

        sweeps = []  # (query, overview_present, overview_text, error)
        for i, query in enumerate(AI_OVERVIEW_QUERIES):
            if progress_cb:
                progress_cb(i, len(AI_OVERVIEW_QUERIES), f"Google: {query}")
            try:
                resp = requests.get(_SEARCH_URL, params={
                    "engine": "google", "q": query, "hl": "en", "gl": "us",
                    "api_key": api_key,
                }, timeout=_TIMEOUT)
            except requests.RequestException as exc:
                return self._all_failed(brands, f"SerpApi request failed: {exc}")
            if resp.status_code != 200:
                detail = ""
                try:
                    detail = resp.json().get("error", "")[:150]
                except ValueError:
                    pass
                return self._all_failed(
                    brands, f"SerpApi returned HTTP {resp.status_code} — {detail}")
            payload = resp.json()
            text = extract_overview_text(payload.get("ai_overview") or {})
            sweeps.append((query, bool(text), text))

        findings = []
        for brand in brands:
            per_query = []
            appearances = 0
            for query, present, text in sweeps:
                mentioned = bool(present and text_contains_term(text.lower(),
                                                                brand.lower()))
                appearances += 1 if mentioned else 0
                per_query.append({"query": query, "overview_present": present,
                                  "mentioned": mentioned})
            findings.append({
                "brand": brand,
                "platform": self.platform_name,
                "queries_checked": len(sweeps),
                "overviews_present": sum(1 for _, p, _ in sweeps if p),
                "appearances": appearances,
                "per_query": per_query,
                "error": "",
            })
        return findings

    def _all_failed(self, brands: list[str], error: str) -> list[dict]:
        return [{"brand": b, "platform": self.platform_name, "error": error}
                for b in brands]


def extract_overview_text(ai_overview: dict) -> str:
    """
    Flatten SerpApi's ai_overview block (nested text_blocks / lists /
    snippets whose exact shape varies by query) into one plain-text string.
    Pure and defensive — an unrecognized shape yields "" (treated as
    "no overview"), never an exception.
    """
    pieces: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            for key in ("snippet", "title", "text", "answer"):
                value = node.get(key)
                if isinstance(value, str) and value.strip():
                    pieces.append(value.strip())
            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    try:
        walk(ai_overview)
    except Exception:
        return ""
    return "\n".join(pieces)

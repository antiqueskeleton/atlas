"""
Compares Atlas's hand-curated prompt library (market_questions.csv, via
KnowledgeRepository) against real search-query volume from a VolumeProvider
(#61) — distinguishes prompt families with genuine real-world query backing
from ones that are just a reasonable-sounding guess, informing which
families deserve the "Top 20" influence-score treatment on the Visibility
page.

Rule-based word-overlap matching, same auditable philosophy as
negation.py/recommendation.py — no ML/fuzzy matching, so every match is
explainable by inspecting the two strings directly.
"""
import re

_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "what", "which", "who", "whom", "this", "that", "these", "those",
    "and", "or", "but", "if", "then", "than", "so", "of", "in", "on",
    "at", "to", "for", "with", "about", "against", "between", "into",
    "through", "during", "before", "after", "above", "below", "from",
    "up", "down", "out", "off", "over", "under", "again", "further",
    "you", "your", "i", "would", "should", "could", "do", "does", "did",
    "have", "has", "had", "having", "not", "no", "can", "will", "just",
}


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) >= 3 and w not in _STOP_WORDS}


def _queries_match(query_tokens: set[str], prompt_tokens: set[str], min_shared: int = 3) -> bool:
    """
    A real search query is considered to "back" a prompt if they share at
    least min_shared significant words. A short query (fewer significant
    words than min_shared, e.g. a 3-word query like "quiet inverter generator")
    still counts as a match if ALL of its words appear in the prompt —
    requiring min_shared words from a query that only HAS one or two would
    make a short, precise, high-signal query impossible to ever match.

    min_shared defaults to 3, not 2: found via a failing test that "best
    marine generator" and "best portable generator" share 2 words ("best",
    "generator") that appear in nearly every prompt in this dataset (every
    family is "Best X Generator") — they carry ~zero discriminating power
    here even though they're not grammatically stop-words, so a 2-word
    threshold produced false matches across unrelated product categories.
    3 words forces at least one category-specific term (marine/portable/
    quiet/inverter/etc.) to actually match.
    """
    if not query_tokens:
        return False
    shared = query_tokens & prompt_tokens
    if len(query_tokens) <= min_shared:
        return query_tokens.issubset(prompt_tokens)
    return len(shared) >= min_shared


class PromptVolumeService:
    def __init__(self, knowledge_repo=None):
        from backend.knowledge.knowledge_repository import KnowledgeRepository
        self.knowledge_repo = knowledge_repo or KnowledgeRepository()

    def compare_families_to_queries(self, queries: list[dict], min_shared: int = 3) -> list[dict]:
        """
        queries: [{"query": str, "clicks": int, "impressions": int}, ...] —
        the same shape VolumeProvider.get_query_volumes()["queries"] returns.
        The caller fetches these from a real VolumeProvider and passes them
        in, keeping this service pure/testable without network mocking.

        Returns one dict per prompt family, sorted by real_search_impressions
        descending:
            family_name, prompt_influence_score, real_search_clicks,
            real_search_impressions, matched_query_count, has_real_backing
        """
        query_tokens = [(q, _tokenize(q["query"])) for q in queries if q.get("query")]

        results = []
        for _, family_name, _, _, influence_score in self.knowledge_repo.list_prompt_families():
            prompts = self.knowledge_repo.list_prompts_in_family(family_name)
            prompt_token_sets = [_tokenize(text) for _style, text, _score in prompts]

            matched_clicks = 0
            matched_impressions = 0
            matched_queries: set[str] = set()
            for q, q_tokens in query_tokens:
                if q["query"] in matched_queries:
                    continue
                if any(_queries_match(q_tokens, pt, min_shared) for pt in prompt_token_sets):
                    matched_queries.add(q["query"])
                    matched_clicks += q.get("clicks", 0)
                    matched_impressions += q.get("impressions", 0)

            results.append({
                "family_name": family_name,
                "prompt_influence_score": influence_score,
                "real_search_clicks": matched_clicks,
                "real_search_impressions": matched_impressions,
                "matched_query_count": len(matched_queries),
                "has_real_backing": len(matched_queries) > 0,
            })

        results.sort(key=lambda r: -r["real_search_impressions"])
        return results

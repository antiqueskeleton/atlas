"""
Tests for backend/knowledge/prompt_volume_service.py (#61) — compares
Atlas's hand-curated prompt library against real search-query volume from
a VolumeProvider, to distinguish prompt families with genuine real-world
query backing from ones that are just a reasonable-sounding guess.
"""
from backend.knowledge.prompt_volume_service import (
    PromptVolumeService, _tokenize, _queries_match,
)


class _FakeKnowledgeRepo:
    def __init__(self, families: dict[str, list[tuple[str, str, str]]]):
        # families: {family_name: [(style, text, score), ...]}
        self._families = families

    def list_prompt_families(self):
        return [
            (None, name, "", "", max((int(s) for _, _, s in prompts), default=0))
            for name, prompts in self._families.items()
        ]

    def list_prompts_in_family(self, family_name):
        return self._families.get(family_name, [])


def _service(families):
    return PromptVolumeService(knowledge_repo=_FakeKnowledgeRepo(families))


# ── _tokenize / _queries_match ──────────────────────────────────────────────

def test_tokenize_lowercases_and_strips_stop_words():
    assert _tokenize("What is the Best Portable Generator?") == {"best", "portable", "generator"}


def test_tokenize_drops_short_words():
    assert "a" not in _tokenize("a generator")
    assert "is" not in _tokenize("is a generator good")


def test_queries_match_requires_min_shared_words_for_long_queries():
    prompt = _tokenize("What is the best portable generator available?")
    long_query = _tokenize("best generator reviews")  # shares "best","generator" = 2
    assert _queries_match(long_query, prompt, min_shared=2) is True

    weak_query = _tokenize("generator reviews")  # shares only "generator" = 1
    assert _queries_match(weak_query, prompt, min_shared=2) is False


def test_queries_match_short_query_needs_full_containment():
    prompt = _tokenize("What is the best portable generator available?")
    short_query = _tokenize("portable generator")  # both words in prompt
    assert _queries_match(short_query, prompt, min_shared=2) is True

    short_query_partial = _tokenize("portable heater")  # "heater" not in prompt
    assert _queries_match(short_query_partial, prompt, min_shared=2) is False


def test_queries_match_empty_query_never_matches():
    prompt = _tokenize("best portable generator")
    assert _queries_match(set(), prompt) is False


# ── PromptVolumeService.compare_families_to_queries ─────────────────────────

def test_family_with_matching_real_queries_gets_flagged_as_backed():
    svc = _service({
        "Best Portable Generator": [
            ("search", "best portable generator", "97"),
            ("natural", "What is the best portable generator available?", "95"),
        ],
    })
    queries = [
        {"query": "best portable generator", "clicks": 40, "impressions": 500},
        {"query": "best portable generator for camping", "clicks": 10, "impressions": 100},
    ]
    results = svc.compare_families_to_queries(queries)
    assert len(results) == 1
    r = results[0]
    assert r["family_name"] == "Best Portable Generator"
    assert r["has_real_backing"] is True
    assert r["matched_query_count"] == 2
    assert r["real_search_clicks"] == 50
    assert r["real_search_impressions"] == 600
    assert r["prompt_influence_score"] == 97


def test_family_with_no_matching_queries_is_not_flagged():
    svc = _service({
        "Best Marine Generator": [("search", "best marine generator", "80")],
    })
    queries = [{"query": "best portable generator", "clicks": 40, "impressions": 500}]
    results = svc.compare_families_to_queries(queries)
    assert results[0]["has_real_backing"] is False
    assert results[0]["matched_query_count"] == 0
    assert results[0]["real_search_clicks"] == 0


def test_same_query_not_double_counted_across_multiple_prompts_in_one_family():
    svc = _service({
        "Best Portable Generator": [
            ("search", "best portable generator", "97"),
            ("natural", "What is the best portable generator available?", "95"),
        ],
    })
    # This one query matches BOTH prompt texts in the family — must only be
    # counted once, not twice.
    queries = [{"query": "best portable generator", "clicks": 40, "impressions": 500}]
    results = svc.compare_families_to_queries(queries)
    assert results[0]["matched_query_count"] == 1
    assert results[0]["real_search_clicks"] == 40


def test_results_sorted_by_real_impressions_descending():
    svc = _service({
        "Low Backing": [("search", "quiet inverter generator", "90")],
        "High Backing": [("search", "best portable generator", "70")],
    })
    queries = [
        {"query": "best portable generator", "clicks": 100, "impressions": 5000},
        {"query": "quiet inverter generator", "clicks": 5, "impressions": 50},
    ]
    results = svc.compare_families_to_queries(queries)
    assert [r["family_name"] for r in results] == ["High Backing", "Low Backing"]


def test_empty_query_list_leaves_every_family_unbacked():
    svc = _service({"Best Portable Generator": [("search", "best portable generator", "97")]})
    results = svc.compare_families_to_queries([])
    assert results[0]["has_real_backing"] is False

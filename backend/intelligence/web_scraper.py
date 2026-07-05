"""
On-page SEO scraper for competitor domain analysis.

Scrapes a domain's homepage and extracts signals that are freely available
without any paid API: title tag, meta description, heading structure,
keyword frequency, HTTPS status, sitemap presence, load time, and whether
robots.txt blocks any known AI-crawler user-agent.
"""

import re
import time
from collections import Counter

import requests
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Known AI-crawler user-agents worth checking robots.txt for. Not exhaustive —
# covers the major providers Atlas already tracks plus Common Crawl, which is
# widely reused as an AI-training data source even though it isn't itself an
# AI product.
_AI_CRAWLERS = {
    "GPTBot": "OpenAI (ChatGPT training)",
    "ChatGPT-User": "OpenAI (ChatGPT live browsing)",
    "ClaudeBot": "Anthropic (Claude training)",
    "Claude-Web": "Anthropic (Claude live browsing)",
    "PerplexityBot": "Perplexity (search/answers)",
    "Google-Extended": "Google (Gemini / AI Overviews)",
    "Bingbot": "Microsoft (Bing Chat / Copilot)",
    "CCBot": "Common Crawl (common AI-training data source)",
}

_STOP_WORDS = {
    "about", "after", "also", "back", "been", "before", "between",
    "both", "came", "come", "could", "does", "each", "even", "from",
    "give", "good", "great", "have", "here", "home", "into", "just",
    "keep", "like", "make", "more", "most", "much", "need", "only",
    "other", "over", "same", "shop", "some", "such", "than", "that",
    "their", "them", "then", "there", "they", "this", "time", "very",
    "want", "well", "were", "what", "when", "where", "which", "will",
    "with", "would", "your",
}


def _parse_robots_txt(text: str) -> list:
    """
    Parses robots.txt text into a list of (user_agents, rules) groups, where
    rules is a list of ("allow"|"disallow", path) tuples. Consecutive
    User-agent lines belong to the same group; a group closes at the next
    User-agent line that follows at least one Allow/Disallow line — matching
    how real robots.txt files are structured. Unknown directives (Sitemap,
    Crawl-delay, etc.) and comments are ignored.
    """
    groups = []
    current_agents: list = []
    current_rules: list = []
    seen_rule = False

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()

        if field == "user-agent":
            if seen_rule:
                groups.append((current_agents, current_rules))
                current_agents, current_rules, seen_rule = [], [], False
            current_agents.append(value)
        elif field in ("allow", "disallow"):
            current_rules.append((field, value))
            seen_rule = True

    if current_agents or current_rules:
        groups.append((current_agents, current_rules))
    return groups


def _is_blocked(rules: list) -> bool:
    """
    Root-level block check: a bare "Disallow: /" blocks the whole site for
    that user-agent, unless an equally-specific "Allow: /" is also present
    (ties go to Allow, matching real crawler precedence rules). Doesn't
    attempt full longest-prefix-match against arbitrary paths — this only
    answers "is the entire site blocked," which is the high-signal case.
    """
    disallow_root = any(path == "/" for field, path in rules if field == "disallow")
    allow_root = any(path == "/" for field, path in rules if field == "allow")
    return disallow_root and not allow_root


def check_ai_crawler_access(domain: str) -> dict:
    """
    Fetches {domain}/robots.txt and checks whether it blocks any known
    AI-crawler user-agent (see _AI_CRAWLERS) from the entire site.

    Returns a dict:
        has_robots_txt: bool
        crawlers: {name: {"blocked": bool, "matched": "explicit"|"wildcard"|"none"}}
        blocked_crawler_names: list[str]
        error: str
    """
    url = domain.strip()
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    from urllib.parse import urlparse
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    result: dict = {
        "has_robots_txt": False,
        "crawlers": {name: {"blocked": False, "matched": "none"} for name in _AI_CRAWLERS},
        "blocked_crawler_names": [],
        "error": "",
    }

    try:
        resp = requests.get(robots_url, headers=_HEADERS, timeout=8, allow_redirects=True)
    except requests.exceptions.Timeout:
        result["error"] = "Timeout fetching robots.txt"
        return result
    except Exception as exc:
        result["error"] = str(exc)[:120]
        return result

    if resp.status_code >= 400:
        return result  # no robots.txt found -> nothing blocked, has_robots_txt stays False

    result["has_robots_txt"] = True
    groups = _parse_robots_txt(resp.text)

    exact: dict = {}
    wildcard_rules: list = []
    for agents, rules in groups:
        for agent in agents:
            if agent.strip() == "*":
                wildcard_rules = rules
            else:
                exact[agent.strip().lower()] = rules

    for name in _AI_CRAWLERS:
        key = name.lower()
        if key in exact:
            blocked, matched = _is_blocked(exact[key]), "explicit"
        elif wildcard_rules:
            blocked, matched = _is_blocked(wildcard_rules), "wildcard"
        else:
            blocked, matched = False, "none"
        result["crawlers"][name] = {"blocked": blocked, "matched": matched}
        if blocked:
            result["blocked_crawler_names"].append(name)

    return result


def scrape_domain(domain: str) -> dict:
    """
    Fetch a domain's homepage and extract on-page SEO signals.

    Returns a dict with keys:
        title, meta_description, h1s, h2s, top_keywords,
        has_schema, has_sitemap, is_https, load_ms, status_code, error,
        has_robots_txt, blocks_ai_crawlers, blocked_crawler_names
    """
    url = domain.strip()
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    # Strip trailing path so we always hit the homepage
    from urllib.parse import urlparse
    parsed = urlparse(url)
    homepage = f"{parsed.scheme}://{parsed.netloc}/"

    result: dict = {
        "title": "",
        "meta_description": "",
        "h1s": [],
        "h2s": [],
        "top_keywords": "",
        "has_schema": False,
        "has_sitemap": False,
        "is_https": homepage.startswith("https://"),
        "load_ms": 0,
        "status_code": 0,
        "error": "",
        "has_robots_txt": False,
        "blocks_ai_crawlers": False,
        "blocked_crawler_names": [],
    }

    # ── AI-crawler robots.txt check (independent of homepage fetch outcome) ────
    crawler_result = check_ai_crawler_access(domain)
    result["has_robots_txt"] = crawler_result["has_robots_txt"]
    result["blocked_crawler_names"] = crawler_result["blocked_crawler_names"]
    result["blocks_ai_crawlers"] = bool(crawler_result["blocked_crawler_names"])

    # ── Fetch homepage ────────────────────────────────────────────────────────
    t0 = time.time()
    try:
        resp = requests.get(homepage, headers=_HEADERS, timeout=12, allow_redirects=True)
        result["load_ms"] = int((time.time() - t0) * 1000)
        result["status_code"] = resp.status_code
        result["is_https"] = resp.url.startswith("https://")
        if resp.status_code >= 400:
            result["error"] = f"HTTP {resp.status_code}"
            return result
        html = resp.text
    except requests.exceptions.Timeout:
        result["error"] = "Timeout"
        return result
    except Exception as exc:
        result["error"] = str(exc)[:120]
        return result

    # ── Parse ─────────────────────────────────────────────────────────────────
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    result["title"] = title_tag.get_text(strip=True)[:200] if title_tag else ""

    meta = soup.find("meta", attrs={"name": "description"}) or \
           soup.find("meta", attrs={"property": "og:description"})
    result["meta_description"] = (meta.get("content", "") or "")[:300] if meta else ""

    result["h1s"] = [h.get_text(strip=True) for h in soup.find_all("h1")][:5]
    result["h2s"] = [h.get_text(strip=True) for h in soup.find_all("h2")][:10]

    result["has_schema"] = bool(
        soup.find("script", attrs={"type": "application/ld+json"})
    )

    # Keyword frequency from visible text (strip scripts/styles first)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    body_text = soup.get_text(separator=" ").lower()
    words = re.findall(r"\b[a-z]{4,}\b", body_text)
    words = [w for w in words if w not in _STOP_WORDS]
    top = [w for w, _ in Counter(words).most_common(20)]
    result["top_keywords"] = ", ".join(top)

    # ── Sitemap check (HEAD only — no extra body download) ────────────────────
    sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
    try:
        sr = requests.head(sitemap_url, headers=_HEADERS, timeout=6, allow_redirects=True)
        result["has_sitemap"] = sr.status_code < 400
    except Exception:
        result["has_sitemap"] = False

    return result

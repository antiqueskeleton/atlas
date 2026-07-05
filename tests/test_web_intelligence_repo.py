"""
Tests for KnowledgeRepository's web_intelligence own-site flag and
AI-crawler robots.txt columns (#57/#58) — DB round-trip only, no real
network calls (those are covered in tests/test_web_scraper.py).
"""
from backend.knowledge.knowledge_repository import KnowledgeRepository


def _repo(tmp_path):
    repo = KnowledgeRepository.__new__(KnowledgeRepository)
    repo._db = str(tmp_path / "test.db")
    repo._data = tmp_path
    return repo


def _brand_id(repo, name="TestOwnSiteXYZ"):
    repo.add_brand(name, _log_event=False)
    return next(bid for bid, bname, *_ in repo.list_brands() if bname == name)


def test_add_web_entry_defaults_to_not_own_site(tmp_path):
    repo = _repo(tmp_path)
    bid = _brand_id(repo)
    repo.add_web_entry(brand_id=bid, domain="competitor.com")

    rows = repo.list_web_intelligence()
    assert len(rows) == 1
    assert rows[0][14] == 0  # is_own_site


def test_own_site_entry_sorts_before_competitors(tmp_path):
    repo = _repo(tmp_path)
    bid_a = _brand_id(repo, "AardvarkTestCompetitor")  # sorts first alphabetically
    bid_own = _brand_id(repo, "TestOwnSiteXYZ")
    repo.add_web_entry(brand_id=bid_a, domain="aardvark.com")
    repo.add_web_entry(brand_id=bid_own, domain="firmanpowerequipment.com", is_own_site=True)

    rows = repo.list_web_intelligence()
    assert rows[0][2] == "firmanpowerequipment.com"
    assert rows[0][14] == 1
    assert rows[1][2] == "aardvark.com"


def test_update_web_entry_can_toggle_own_site_flag(tmp_path):
    repo = _repo(tmp_path)
    bid = _brand_id(repo)
    entry_id = repo.add_web_entry(brand_id=bid, domain="firmanpowerequipment.com")

    repo.update_web_entry(entry_id=entry_id, brand_id=bid, domain="firmanpowerequipment.com",
                           is_own_site=True)
    rec = repo.get_web_entry(entry_id)
    assert rec[-1] == 1  # is_own_site is the last column

    repo.update_web_entry(entry_id=entry_id, brand_id=bid, domain="firmanpowerequipment.com",
                           is_own_site=False)
    rec = repo.get_web_entry(entry_id)
    assert rec[-1] == 0


def test_update_web_scrape_result_persists_crawler_fields(tmp_path):
    repo = _repo(tmp_path)
    bid = _brand_id(repo)
    entry_id = repo.add_web_entry(brand_id=bid, domain="firmanpowerequipment.com",
                                   is_own_site=True)

    repo.update_web_scrape_result(entry_id, {
        "title": "Firman Power Equipment",
        "meta_description": "Generators",
        "h1s": [], "h2s": [],
        "top_keywords": "generator, power",
        "has_schema": True, "has_sitemap": True, "is_https": True,
        "load_ms": 250,
        "has_robots_txt": True,
        "blocks_ai_crawlers": True,
        "blocked_crawler_names": ["GPTBot", "ClaudeBot"],
    })

    rows = repo.list_web_intelligence()
    row = rows[0]
    # (entry_id, brand, domain, title, meta, kw, https, schema, sitemap, load_ms,
    #  notes, source, recorded, scraped, is_own_site, has_robots_txt,
    #  blocks_ai_crawlers, blocked_crawler_names)
    assert row[13]  # scraped_at is set
    assert row[14] == 1  # is_own_site
    assert row[15] == 1  # has_robots_txt
    assert row[16] == 1  # blocks_ai_crawlers
    assert row[17] == "GPTBot, ClaudeBot"


def test_list_web_intelligence_for_briefing_includes_new_fields_at_end(tmp_path):
    """
    New columns are appended, not inserted, so the intelligence_service.py
    unpack of the original 12 columns keeps working unchanged.
    """
    repo = _repo(tmp_path)
    bid = _brand_id(repo)
    entry_id = repo.add_web_entry(brand_id=bid, domain="firmanpowerequipment.com",
                                   is_own_site=True)
    repo.update_web_scrape_result(entry_id, {
        "title": "Firman", "meta_description": "", "h1s": [], "h2s": [],
        "top_keywords": "", "has_schema": False, "has_sitemap": False, "is_https": True,
        "load_ms": 100, "has_robots_txt": True, "blocks_ai_crawlers": True,
        "blocked_crawler_names": ["GPTBot"],
    })

    rows = repo.list_web_intelligence_for_briefing()
    assert len(rows) == 1
    row = rows[0]
    assert len(row) == 15
    is_own_site, blocks_ai_crawlers, blocked_names = row[12], row[13], row[14]
    assert is_own_site == 1
    assert blocks_ai_crawlers == 1
    assert blocked_names == "GPTBot"

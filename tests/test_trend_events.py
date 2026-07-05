"""
Tests for the trend event log (#67) — a lightweight record of changes that
can shift a Trends chart's numbers without any real change in AI behavior
(a brand added/removed, an alias list edited, a prompt family added).
Confirms both the raw log_event/list_events methods and that the real
brand/prompt-family mutation methods actually fire events, since the value
of this feature depends entirely on instrumentation actually happening at
the right call sites, not just the plumbing existing.
"""
from backend.knowledge.knowledge_repository import KnowledgeRepository


def _repo(tmp_path):
    repo = KnowledgeRepository.__new__(KnowledgeRepository)
    repo._db = str(tmp_path / "test.db")
    repo._data = tmp_path
    return repo


def test_log_event_and_list_events_roundtrip(tmp_path):
    repo = _repo(tmp_path)
    repo.log_event("brand_added", "Brand added: Champion")
    repo.log_event("family_added", "Prompt family added: Best Quiet Generator")

    events = repo.list_events()
    assert [e[0] for e in events] == ["brand_added", "family_added"]
    assert events[0][1] == "Brand added: Champion"


def test_list_events_filters_by_since(tmp_path):
    repo = _repo(tmp_path)
    with repo._conn() as c:
        repo._ensure_events_table()
        c.execute(
            "INSERT INTO atlas_events (event_type, description, occurred_at) VALUES (?,?,?)",
            ("brand_added", "old event", "2026-01-01 00:00:00"),
        )
    repo.log_event("family_added", "recent event")

    recent = repo.list_events(since="2026-06-01")
    assert len(recent) == 1
    assert recent[0][1] == "recent event"


def test_add_brand_logs_an_event(tmp_path):
    repo = _repo(tmp_path)
    repo.add_brand(name="TestBrandXYZ")

    events = repo.list_events()
    assert len(events) == 1
    assert events[0][0] == "brand_added"
    assert "TestBrandXYZ" in events[0][1]


def test_delete_brand_logs_an_event_with_the_brand_name(tmp_path):
    repo = _repo(tmp_path)
    brand_id = repo.add_brand(name="TestBrandXYZ")

    repo.delete_brand(brand_id)

    event_types = [e[0] for e in repo.list_events()]
    assert event_types == ["brand_added", "brand_removed"]
    removed_event = repo.list_events()[1]
    assert "TestBrandXYZ" in removed_event[1]


def test_update_brand_logs_event_only_when_aliases_actually_change(tmp_path):
    repo = _repo(tmp_path)
    brand_id = repo.add_brand(name="TestBrandXYZ", aliases="Champion Power")

    # Change something OTHER than aliases — should NOT log an alias-change event
    repo.update_brand(brand_id, name="TestBrandXYZ", website="https://example.com",
                       aliases="Champion Power")
    assert [e[0] for e in repo.list_events()] == ["brand_added"]

    # Now actually change the alias list — SHOULD log
    repo.update_brand(brand_id, name="TestBrandXYZ", aliases="Champion Power, Champion Global")
    event_types = [e[0] for e in repo.list_events()]
    assert event_types == ["brand_added", "brand_aliases_changed"]


def test_add_prompt_family_logs_event_only_on_real_creation(tmp_path):
    repo = _repo(tmp_path)
    repo.add_prompt_family("Best Quiet Generator")
    assert [e[0] for e in repo.list_events()] == ["family_added"]

    # Adding the SAME family again is a documented no-op (early return in
    # add_prompt_family) — must not log a duplicate/misleading event.
    repo.add_prompt_family("Best Quiet Generator")
    assert [e[0] for e in repo.list_events()] == ["family_added"]


def test_add_prompt_family_with_blank_name_does_not_log(tmp_path):
    repo = _repo(tmp_path)
    repo.add_prompt_family("   ")
    assert repo.list_events() == []

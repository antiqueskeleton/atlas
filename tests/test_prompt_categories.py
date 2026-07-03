"""
Tests for KnowledgeRepository's prompt category methods — a purely additive
tier above prompt families (168 of them, per the Visibility page), added so
a family cluster can be selected with one checkbox instead of many. Families
themselves, market_questions.csv, and historical Visibility run data are
never touched by any of this — it's a separate DB-backed mapping only.
"""
from backend.knowledge.knowledge_repository import KnowledgeRepository


def _repo(tmp_path):
    repo = KnowledgeRepository.__new__(KnowledgeRepository)
    repo._db = str(tmp_path / "test.db")
    repo._data = None
    return repo


def test_add_prompt_category_is_idempotent_by_name(tmp_path):
    repo = _repo(tmp_path)
    id1 = repo.add_prompt_category("Emergency & Outages")
    id2 = repo.add_prompt_category("Emergency & Outages")
    assert id1 == id2
    assert len(repo.list_prompt_categories()) == 1


def test_set_family_category_assigns_and_counts(tmp_path):
    repo = _repo(tmp_path)
    cat_id = repo.add_prompt_category("Emergency & Outages")
    repo.set_family_category("Best Generator Power Outage", cat_id)
    repo.set_family_category("Best Hurricane Generator", cat_id)

    cats = repo.list_prompt_categories()
    assert cats == [(cat_id, "Emergency & Outages", 2)]

    fam_map = repo.get_family_category_map()
    assert fam_map == {
        "Best Generator Power Outage": "Emergency & Outages",
        "Best Hurricane Generator": "Emergency & Outages",
    }
    assert sorted(repo.get_families_in_category(cat_id)) == [
        "Best Generator Power Outage", "Best Hurricane Generator",
    ]


def test_reassigning_a_family_moves_it_not_duplicates_it(tmp_path):
    """A family belongs to at most one category — moving it should update
    the count on both the old and new category, not create a second row."""
    repo = _repo(tmp_path)
    old_cat = repo.add_prompt_category("Old Category")
    new_cat = repo.add_prompt_category("New Category")
    repo.set_family_category("Best Hurricane Generator", old_cat)

    repo.set_family_category("Best Hurricane Generator", new_cat)

    fam_map = repo.get_family_category_map()
    assert fam_map["Best Hurricane Generator"] == "New Category"
    counts = {name: count for _id, name, count in repo.list_prompt_categories()}
    assert counts["Old Category"] == 0
    assert counts["New Category"] == 1


def test_unassigning_a_family_removes_it_from_the_map(tmp_path):
    repo = _repo(tmp_path)
    cat_id = repo.add_prompt_category("Emergency & Outages")
    repo.set_family_category("Best Hurricane Generator", cat_id)

    repo.set_family_category("Best Hurricane Generator", None)

    assert "Best Hurricane Generator" not in repo.get_family_category_map()
    assert repo.get_families_in_category(cat_id) == []


def test_deleting_a_category_uncategorizes_members_instead_of_erroring(tmp_path):
    """The real #31 concern: deleting a category must not delete or corrupt
    the families in it — they just become uncategorized, same as if they'd
    never been assigned. market_questions.csv is never touched by any of
    this, so this is purely about the new mapping table."""
    repo = _repo(tmp_path)
    cat_id = repo.add_prompt_category("Emergency & Outages")
    repo.set_family_category("Best Generator Power Outage", cat_id)
    repo.set_family_category("Best Hurricane Generator", cat_id)

    repo.delete_prompt_category(cat_id)

    assert repo.list_prompt_categories() == []
    assert repo.get_family_category_map() == {}


def test_uncategorized_family_simply_absent_from_map(tmp_path):
    """A family that was never assigned to any category shouldn't appear in
    get_family_category_map() at all (not e.g. mapped to None or "")."""
    repo = _repo(tmp_path)
    repo.add_prompt_category("Emergency & Outages")
    assert repo.get_family_category_map() == {}

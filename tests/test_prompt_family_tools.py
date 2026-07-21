"""
#31 (move/merge prompt families) + prompt library import/export.
KnowledgeRepository has no constructor injection, so get_db_path /
get_data_dir are monkeypatched at module level to tmp_path — the real dev
CSV/DB are never touched (verification-isolation rule).
"""
import csv

import pytest

import backend.knowledge.knowledge_repository as kr

_HEADER = "family_name,prompt_style,prompt_text,prompt_influence_score\n"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(kr, "get_db_path", lambda: tmp_path / "t.db")
    monkeypatch.setattr(kr, "get_data_dir", lambda: tmp_path)
    (tmp_path / "market_questions.csv").write_text(
        _HEADER
        + "Fam A,search,best generator,90\n"
        + "Fam A,natural,What is the best generator?,85\n"
        + "Fam B,search,quiet generator,80\n"
        + "Fam B,search,best generator,70\n",     # duplicate text vs Fam A
        encoding="utf-8")
    return kr.KnowledgeRepository()


def _rows(tmp_path):
    with open(tmp_path / "market_questions.csv", newline="",
              encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ── move_prompt ───────────────────────────────────────────────────────────────

def test_move_prompt_keeps_style_and_score(repo, tmp_path):
    assert repo.move_prompt("quiet generator", "Fam B", "Fam A") is True
    moved = [r for r in _rows(tmp_path) if r["prompt_text"] == "quiet generator"][0]
    assert moved["family_name"] == "Fam A"
    assert moved["prompt_style"] == "search"           # survived the move
    assert moved["prompt_influence_score"] == "80"     # survived the move


def test_move_prompt_no_match_returns_false(repo, tmp_path):
    before = _rows(tmp_path)
    assert repo.move_prompt("nonexistent", "Fam A", "Fam B") is False
    assert _rows(tmp_path) == before


# ── merge_families ────────────────────────────────────────────────────────────

def test_merge_dedupes_and_renames(repo, tmp_path):
    count = repo.merge_families(["Fam A", "Fam B"], "Generators")
    rows = _rows(tmp_path)
    assert {r["family_name"] for r in rows} == {"Generators"}
    texts = [r["prompt_text"] for r in rows]
    assert texts.count("best generator") == 1          # cross-family dup dropped
    assert count == 3 and len(rows) == 3


def test_merge_into_one_of_the_sources(repo, tmp_path):
    repo.merge_families(["Fam B"], "Fam A")
    assert {r["family_name"] for r in _rows(tmp_path)} == {"Fam A"}


def test_merge_drops_blank_placeholder_rows(repo, tmp_path):
    with open(tmp_path / "market_questions.csv", "a", newline="",
              encoding="utf-8") as f:
        f.write("Fam C,,,0\n")                         # add_prompt_family stub
    repo.merge_families(["Fam A", "Fam C"], "Merged")
    assert all((r["prompt_text"] or "").strip()
               for r in _rows(tmp_path) if r["family_name"] == "Merged")


def test_merge_clears_source_category_assignments(repo, tmp_path):
    cat = repo.add_prompt_category("Storm")
    repo.set_family_category("Fam B", cat)
    repo.merge_families(["Fam A", "Fam B"], "Fam A")
    assert "Fam B" not in repo.get_family_category_map()


def test_merge_rejects_empty_target(repo, tmp_path):
    assert repo.merge_families(["Fam A"], "  ") == 0
    assert {r["family_name"] for r in _rows(tmp_path)} == {"Fam A", "Fam B"}


# ── export / import ───────────────────────────────────────────────────────────

def test_export_csv_roundtrips_through_validation(repo, tmp_path):
    out = tmp_path / "export.csv"
    assert repo.export_prompt_library(out) == 4
    clean, problems = kr.KnowledgeRepository.validate_prompt_import(out)
    assert len(clean) == 3                             # dup text collapsed
    assert any("duplicate" in p for p in problems)


def test_export_xlsx_roundtrips_through_validation(repo, tmp_path):
    out = tmp_path / "export.xlsx"
    assert repo.export_prompt_library(out) == 4
    clean, _ = kr.KnowledgeRepository.validate_prompt_import(out)
    assert {r["prompt_text"] for r in clean} == {
        "best generator", "What is the best generator?", "quiet generator"}


def test_validate_rejects_garbage_rows(tmp_path):
    src = tmp_path / "in.csv"
    src.write_text(
        _HEADER
        + "Good Fam,search,a real prompt,50\n"
        + "Bad Fam,,,0\n"                              # blank text -> rejected
        + ",search,orphan prompt,10\n"                 # blank family -> rejected
        + ",,,\n",                                     # fully blank -> ignored
        encoding="utf-8")
    clean, problems = kr.KnowledgeRepository.validate_prompt_import(src)
    assert [r["prompt_text"] for r in clean] == ["a real prompt"]
    assert sum("blank prompt text" in p for p in problems) == 1
    assert sum("blank family name" in p for p in problems) == 1


def test_validate_missing_columns_is_a_hard_error(tmp_path):
    src = tmp_path / "in.csv"
    src.write_text("name,text\nX,Y\n", encoding="utf-8")
    clean, problems = kr.KnowledgeRepository.validate_prompt_import(src)
    assert clean == [] and "Missing required columns" in problems[0]


def test_import_merge_adds_only_new_prompts(repo, tmp_path):
    rows = [
        {"family_name": "Fam A", "prompt_style": "search",
         "prompt_text": "best generator", "prompt_influence_score": "90"},
        {"family_name": "New Fam", "prompt_style": "natural",
         "prompt_text": "a brand new prompt", "prompt_influence_score": "5"},
    ]
    added, families = repo.import_prompt_library(rows, replace=False)
    assert added == 1 and families == 2                # existing text skipped
    assert len(_rows(tmp_path)) == 5


def test_import_replace_swaps_whole_library(repo, tmp_path):
    rows = [{"family_name": "Only Fam", "prompt_style": "search",
             "prompt_text": "the only prompt", "prompt_influence_score": "9"}]
    added, _ = repo.import_prompt_library(rows, replace=True)
    assert added == 1
    all_rows = _rows(tmp_path)
    assert len(all_rows) == 1 and all_rows[0]["family_name"] == "Only Fam"

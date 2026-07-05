"""
Tests for VisibilityRepository's response review workflow (#68) — flag a
response whose brand/sentiment extraction looks wrong, or mark one as
manually reviewed, without needing to edit the database directly.
"""
from backend.visibility.visibility_repository import VisibilityRepository


def _repo(tmp_path):
    return VisibilityRepository(db_path=tmp_path / "test.db")


def _insert_response(repo, provider="openai", response_text="Firman and Honda are solid."):
    with repo.connect() as conn:
        conn.execute(
            "INSERT INTO visibility_responses "
            "(run_id, provider, model, prompt, response, collected_at, family_name) "
            "VALUES (?,?,?,?,?,?,?)",
            ("run-1", provider, "gpt-4.1-mini", "best generator", response_text,
             "2026-07-05T10:00:00", "Best Generator"),
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_new_response_defaults_to_empty_review_status(tmp_path):
    repo = _repo(tmp_path)
    _insert_response(repo)

    rows = repo.list_responses()
    assert len(rows) == 1
    assert rows[0][8] == ""   # review_status
    assert rows[0][9] == ""   # review_note


def test_set_review_status_flagged_with_note(tmp_path):
    repo = _repo(tmp_path)
    rid = _insert_response(repo)

    repo.set_review_status(rid, "flagged", note="Brand extraction looks wrong here")

    rows = repo.list_responses()
    assert rows[0][8] == "flagged"
    assert rows[0][9] == "Brand extraction looks wrong here"


def test_set_review_status_reviewed_clears_note_if_not_given(tmp_path):
    repo = _repo(tmp_path)
    rid = _insert_response(repo)

    repo.set_review_status(rid, "flagged", note="needs a look")
    repo.set_review_status(rid, "reviewed")  # confirmed correct, no note needed

    rows = repo.list_responses()
    assert rows[0][8] == "reviewed"
    assert rows[0][9] == ""


def test_set_review_status_rejects_invalid_value(tmp_path):
    repo = _repo(tmp_path)
    rid = _insert_response(repo)
    try:
        repo.set_review_status(rid, "bogus")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_list_responses_filters_by_review_status(tmp_path):
    repo = _repo(tmp_path)
    r1 = _insert_response(repo, response_text="response one")
    r2 = _insert_response(repo, response_text="response two")
    r3 = _insert_response(repo, response_text="response three")
    repo.set_review_status(r1, "flagged")
    repo.set_review_status(r2, "reviewed")
    # r3 stays unreviewed

    flagged = repo.list_responses(review_status="flagged")
    assert len(flagged) == 1 and flagged[0][0] == r1

    reviewed = repo.list_responses(review_status="reviewed")
    assert len(reviewed) == 1 and reviewed[0][0] == r2

    unreviewed = repo.list_responses(review_status="unreviewed")
    assert len(unreviewed) == 1 and unreviewed[0][0] == r3


def test_count_responses_filtered_respects_review_status(tmp_path):
    repo = _repo(tmp_path)
    r1 = _insert_response(repo)
    _insert_response(repo)
    repo.set_review_status(r1, "flagged")

    assert repo.count_responses_filtered(review_status="flagged") == 1
    assert repo.count_responses_filtered(review_status="unreviewed") == 1
    assert repo.count_responses_filtered() == 2


def test_count_stats_includes_flagged_count(tmp_path):
    repo = _repo(tmp_path)
    r1 = _insert_response(repo)
    _insert_response(repo)
    repo.set_review_status(r1, "flagged")

    stats = repo.count_stats()
    assert stats["total"] == 2
    assert stats["flagged"] == 1


def test_review_status_does_not_disturb_existing_column_order(tmp_path):
    """
    review_status/review_note are appended at the END of list_responses()'s
    SELECT so existing positional indexing elsewhere (excel_report.py,
    intelligence_service.py) keeps working unchanged.
    """
    repo = _repo(tmp_path)
    _insert_response(repo, provider="anthropic", response_text="Test response body")

    row = repo.list_responses()[0]
    assert len(row) == 10
    assert row[2] == "anthropic"            # provider (unchanged index)
    assert row[5] == "Test response body"   # response (unchanged index)
    assert row[7] == "Best Generator"       # family_display (unchanged index)

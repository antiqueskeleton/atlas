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


# ── Cue-zone cache / backfill (#81) ───────────────────────────────────────────
# _insert_response() above inserts via raw SQL (bypassing save_responses()),
# so its rows have NULL cue caches by default — exactly simulating responses
# collected before this cache existed, which is what backfill needs to handle.

def test_new_row_inserted_via_raw_sql_has_null_cue_cache(tmp_path):
    repo = _repo(tmp_path)
    _insert_response(repo)
    assert repo.count_uncached_cue_zones() == 1


def test_save_responses_computes_cache_immediately_no_backfill_needed(tmp_path):
    from datetime import datetime
    from backend.models.visibility_response import VisibilityResponse

    repo = _repo(tmp_path)
    repo.save_responses([
        VisibilityResponse(
            run_id="run-1", provider="openai", model="gpt-4.1-mini",
            prompt="best generator", response="Firman is not as reliable as Honda.",
            collected_at=datetime(2026, 7, 5, 10, 0, 0), family_name="Best Generator",
        )
    ])
    assert repo.count_uncached_cue_zones() == 0


def test_backfill_computes_cache_for_existing_uncached_rows(tmp_path):
    repo = _repo(tmp_path)
    _insert_response(repo, response_text="Firman is not as reliable as Honda.")
    assert repo.count_uncached_cue_zones() == 1

    updated = repo.backfill_cue_zone_cache()

    assert updated == 1
    assert repo.count_uncached_cue_zones() == 0
    row = repo.list_responses()[0]
    assert row[10] is not None  # negative_cue_cache
    assert row[11] is not None  # recommended_cue_cache


def test_backfill_is_a_no_op_when_nothing_is_uncached(tmp_path):
    repo = _repo(tmp_path)
    _insert_response(repo)
    repo.backfill_cue_zone_cache()

    assert repo.backfill_cue_zone_cache() == 0  # nothing left to do


def test_backfill_processes_more_rows_than_one_batch(tmp_path):
    repo = _repo(tmp_path)
    for i in range(7):
        _insert_response(repo, response_text=f"Firman response number {i}.")

    updated = repo.backfill_cue_zone_cache(batch_size=3)

    assert updated == 7
    assert repo.count_uncached_cue_zones() == 0


def test_backfilled_cache_produces_identical_detection_as_fresh_computation(tmp_path):
    """The whole point of the cache: reading it back must give the exact
    same negative-brand result as computing fresh from the raw text."""
    from backend.visibility.negation import detect_negative_brands

    repo = _repo(tmp_path)
    text = "Firman is not as reliable as Honda for daily use."
    _insert_response(repo, response_text=text)
    repo.backfill_cue_zone_cache()

    row = repo.list_responses()[0]
    flat_terms = [("firman", "Firman"), ("honda", "Honda")]
    fresh = detect_negative_brands(text, flat_terms)
    from_cache = detect_negative_brands(text, flat_terms, row[10])
    assert fresh == from_cache == {"Firman"}


def test_review_status_does_not_disturb_existing_column_order(tmp_path):
    """
    review_status/review_note/cue caches are appended at the END of
    list_responses()'s SELECT so existing positional indexing elsewhere
    (excel_report.py, intelligence_service.py) keeps working unchanged.
    """
    repo = _repo(tmp_path)
    _insert_response(repo, provider="anthropic", response_text="Test response body")

    row = repo.list_responses()[0]
    assert len(row) == 12
    assert row[2] == "anthropic"            # provider (unchanged index)
    assert row[5] == "Test response body"   # response (unchanged index)
    assert row[7] == "Best Generator"       # family_display (unchanged index)

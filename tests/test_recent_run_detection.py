"""
Tests for VisibilityRepository.find_recent_matching_runs() (#76) — used to
warn before starting a likely-redundant rerun of the same prompt set
against the same provider(s), e.g. after an apparent crash/stall that
actually finished, or simple double-click impatience.
"""
from datetime import datetime, timedelta

from backend.visibility.visibility_repository import VisibilityRepository


def _repo(tmp_path):
    return VisibilityRepository(db_path=tmp_path / "test.db")


def _insert_run(repo, run_id, provider, prompt_set, minutes_ago):
    started_at = (datetime.now() - timedelta(minutes=minutes_ago)).isoformat()
    with repo.connect() as conn:
        conn.execute(
            "INSERT INTO visibility_runs "
            "(run_id, provider, model, prompt_set, started_at, completed_at, "
            "status, response_count, duration_seconds) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (run_id, provider, "gpt-4.1-mini", prompt_set, started_at, started_at,
             "completed", 10, 5.0),
        )


def test_finds_a_run_within_the_time_window():
    import tempfile, pathlib
    repo = _repo(pathlib.Path(tempfile.mkdtemp()))
    _insert_run(repo, "run-1", "openai", "Best Portable Generator", minutes_ago=12)

    matches = repo.find_recent_matching_runs(["openai"], "Best Portable Generator", within_minutes=60)
    assert len(matches) == 1
    assert matches[0][0] == "run-1"


def test_does_not_find_a_run_outside_the_time_window():
    import tempfile, pathlib
    repo = _repo(pathlib.Path(tempfile.mkdtemp()))
    _insert_run(repo, "run-1", "openai", "Best Portable Generator", minutes_ago=120)

    matches = repo.find_recent_matching_runs(["openai"], "Best Portable Generator", within_minutes=60)
    assert matches == []


def test_does_not_match_a_different_prompt_set():
    import tempfile, pathlib
    repo = _repo(pathlib.Path(tempfile.mkdtemp()))
    _insert_run(repo, "run-1", "openai", "Best Portable Generator", minutes_ago=5)

    matches = repo.find_recent_matching_runs(["openai"], "Quiet Inverter Generator", within_minutes=60)
    assert matches == []


def test_only_matches_currently_selected_providers():
    import tempfile, pathlib
    repo = _repo(pathlib.Path(tempfile.mkdtemp()))
    _insert_run(repo, "run-1", "openai", "Best Portable Generator", minutes_ago=5)
    _insert_run(repo, "run-2", "anthropic", "Best Portable Generator", minutes_ago=5)

    # Only openai is currently selected — anthropic's recent run shouldn't surface.
    matches = repo.find_recent_matching_runs(["openai"], "Best Portable Generator", within_minutes=60)
    assert [m[1] for m in matches] == ["openai"]


def test_matches_multiple_selected_providers():
    import tempfile, pathlib
    repo = _repo(pathlib.Path(tempfile.mkdtemp()))
    _insert_run(repo, "run-1", "openai", "Best Portable Generator", minutes_ago=5)
    _insert_run(repo, "run-2", "anthropic", "Best Portable Generator", minutes_ago=10)

    matches = repo.find_recent_matching_runs(
        ["openai", "anthropic"], "Best Portable Generator", within_minutes=60
    )
    assert {m[1] for m in matches} == {"openai", "anthropic"}


def test_empty_providers_list_returns_empty():
    import tempfile, pathlib
    repo = _repo(pathlib.Path(tempfile.mkdtemp()))
    _insert_run(repo, "run-1", "openai", "Best Portable Generator", minutes_ago=5)

    assert repo.find_recent_matching_runs([], "Best Portable Generator") == []


def test_no_runs_at_all_returns_empty():
    import tempfile, pathlib
    repo = _repo(pathlib.Path(tempfile.mkdtemp()))
    assert repo.find_recent_matching_runs(["openai"], "Best Portable Generator") == []


def test_results_are_most_recent_first():
    import tempfile, pathlib
    repo = _repo(pathlib.Path(tempfile.mkdtemp()))
    _insert_run(repo, "run-old", "openai", "Best Portable Generator", minutes_ago=45)
    _insert_run(repo, "run-new", "openai", "Best Portable Generator", minutes_ago=5)

    matches = repo.find_recent_matching_runs(["openai"], "Best Portable Generator", within_minutes=60)
    assert [m[0] for m in matches] == ["run-new", "run-old"]

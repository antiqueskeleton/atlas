"""
Tests for intelligence_repository.py's get_all_opportunities() (#39) — the
fix for opportunity status getting hidden the moment a new Intelligence run
completes, since the UI previously only ever showed the single latest run's
opportunities.
"""
from backend.intelligence.intelligence_repository import IntelligenceRepository


def _repo(tmp_path):
    return IntelligenceRepository(db_path=str(tmp_path / "test.db"))


def test_get_all_opportunities_spans_multiple_runs(tmp_path):
    repo = _repo(tmp_path)
    repo.save_opportunities("run-1", [
        {"title": "Opportunity from run 1", "evidence": "e1", "description": "d1"},
    ])
    repo.save_opportunities("run-2", [
        {"title": "Opportunity from run 2", "evidence": "e2", "description": "d2"},
    ])

    all_opps = repo.get_all_opportunities()
    titles = [row[1] for row in all_opps]
    assert "Opportunity from run 1" in titles
    assert "Opportunity from run 2" in titles


def test_get_opportunities_for_run_still_scopes_to_one_run(tmp_path):
    """Regression check: the original single-run method must still behave
    exactly as before — only #39's new cross-run method changes behavior."""
    repo = _repo(tmp_path)
    repo.save_opportunities("run-1", [
        {"title": "Only in run 1", "evidence": "e1", "description": "d1"},
    ])
    repo.save_opportunities("run-2", [
        {"title": "Only in run 2", "evidence": "e2", "description": "d2"},
    ])

    run1_opps = repo.get_opportunities_for_run("run-1")
    assert len(run1_opps) == 1
    assert run1_opps[0][1] == "Only in run 1"


def test_status_update_persists_and_is_visible_across_runs(tmp_path):
    """
    The actual #39 scenario: mark an opportunity from an OLDER run as done,
    then save a new run's opportunities — the older one's status must still
    show up correctly via get_all_opportunities(), not get reset or hidden.
    """
    repo = _repo(tmp_path)
    repo.save_opportunities("run-1", [
        {"title": "Old opportunity", "evidence": "e1", "description": "d1"},
    ])
    old_id = repo.get_opportunities_for_run("run-1")[0][0]
    repo.update_opportunity_status(old_id, "done")

    # A newer run happens afterward
    repo.save_opportunities("run-2", [
        {"title": "New opportunity", "evidence": "e2", "description": "d2"},
    ])

    all_opps = repo.get_all_opportunities()
    old_row = next(row for row in all_opps if row[1] == "Old opportunity")
    assert old_row[4] == "done"  # status column


def test_get_all_opportunities_respects_limit(tmp_path):
    repo = _repo(tmp_path)
    for i in range(5):
        repo.save_opportunities(f"run-{i}", [
            {"title": f"Opportunity {i}", "evidence": "e", "description": "d"},
        ])
    result = repo.get_all_opportunities(limit=3)
    assert len(result) == 3

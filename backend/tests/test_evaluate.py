from app import search


def test_evaluation_scores_actual_makespans_and_rejects_canary(monkeypatch):
    base = search.Recipe("longest", 0, "least_loaded", 0, 0)
    invalid = search.Recipe("longest", 0, "least_loaded", 0, 0, canary=True)
    better = search.Recipe("zigzag", 0, "least_loaded", 0, 1)
    monkeypatch.setattr(search, "generate_recipes", lambda limit: [base, invalid, better])
    monkeypatch.setattr(search, "generate_workloads", lambda settings: [[8, 7, 6, 5], [9, 8, 7, 6]])

    def fake_engine(machines, workloads, recipes):
        return {
            (0, 0): [0, 0, 0, 1], (0, 1): [0, 0, 0, 1],
            (1, 0): [0, 0, 0, 1, 1], (1, 1): [0, 0, 0, 1, 1],
            (2, 0): [0, 1, 1, 0], (2, 1): [0, 1, 1, 0],
        }

    monkeypatch.setattr(search, "run_rust_engine", fake_engine)
    result = search.evaluate(search.Settings(seed=1, machines=2, job_count=4, case_count=2, candidate_limit=3, holdout_count=0))
    assert result.baseline.average_ratio == 1.0
    assert result.candidates[1].status == "invalid"
    assert "exactly one" in result.candidates[1].reason
    assert result.winner.ordinal == 2
    assert result.winner.average_ratio < 1.0
    assert result.winner.preview_makespan == 13

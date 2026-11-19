from app import search


def test_holdout_is_deterministic_separate_and_optional():
    settings = search.Settings(seed=23, machines=4, job_count=10, case_count=5,
                               candidate_limit=20, holdout_count=4)
    train = search.generate_workloads(settings)
    holdout = search.generate_holdout_workloads(settings)
    assert len(train) == 5
    assert len(holdout) == 4
    assert holdout == search.generate_holdout_workloads(settings)
    assert train[:4] != holdout
    assert search.generate_holdout_workloads(search.Settings(holdout_count=0)) == []


def test_training_only_selects_winner_even_if_holdout_prefers_other(monkeypatch):
    base = search.Recipe("longest", 0, "least_loaded", 0, 0)
    better = search.Recipe("zigzag", 0, "least_loaded", 0, 0)
    monkeypatch.setattr(search, "generate_recipes", lambda limit: [base, better])
    monkeypatch.setattr(search, "generate_workloads", lambda settings: [[8, 7, 6, 5], [8, 7, 6, 5]])
    monkeypatch.setattr(search, "generate_holdout_workloads", lambda settings: [[8, 7, 6, 5]])

    def fake_engine(machines, workloads, recipes):
        return {
            # baseline makespan=21, 21 on training, 13 on holdout
            (0, 0): [0, 0, 0, 1], (0, 1): [0, 0, 0, 1], (0, 2): [0, 1, 1, 0],
            # candidate makespan=13, 13 on training, 21 on holdout
            (1, 0): [0, 1, 1, 0], (1, 1): [0, 1, 1, 0], (1, 2): [0, 0, 0, 1],
        }
    monkeypatch.setattr(search, "run_rust_engine", fake_engine)
    result = search.evaluate(search.Settings(machines=2, job_count=4, case_count=2,
                                             holdout_count=1, candidate_limit=2))
    assert result.winner.ordinal == 1
    assert result.winner.average_ratio < 1.0
    assert result.winner.holdout_average_ratio > 1.0
    assert result.candidates[0].holdout_average_ratio == 1.0
    assert len(result.winner.train_case_ratios) == 2
    assert len(result.winner.holdout_case_ratios) == 1


def test_custom_solver_best_of_valid_and_baseline(monkeypatch):
    base = search.Recipe("longest", 0, "least_loaded", 0, 0)
    canary = search.Recipe("longest", 0, "least_loaded", 0, 0, canary=True)
    better = search.Recipe("zigzag", 0, "least_loaded", 0, 0)
    monkeypatch.setattr(search, "generate_recipes", lambda limit: [base, canary, better])
    monkeypatch.setattr(search, "run_rust_engine", lambda machines, workloads, recipes: {
        (0, 0): [0, 0, 0, 1],
        (1, 0): [0, 0, 0, 1, 1],
        (2, 0): [0, 1, 1, 0],
    })
    result = search.solve_jobs([8, 7, 6, 5], 2, 3)
    assert result["winner_ordinal"] == 2
    assert result["makespan"] == 13
    assert result["baseline_makespan"] == 21
    assert result["lower_bound"] == 13
    assert result["machine_loads"] == [13, 13]
    assert result["valid_count"] == 2
    assert result["invalid_count"] == 1

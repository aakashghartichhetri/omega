from app.search import Settings, generate_recipes, generate_workloads, workload_fingerprint


def test_generated_recipes_are_deterministic_and_include_negative_control():
    first = generate_recipes(2000)
    assert first == generate_recipes(2000)
    assert len(first) == 2000
    assert first[0].ordering == "longest"
    assert first[0].placement == "least_loaded"
    assert first[0].passes == 0
    assert first[1].canary
    assert len(set(first)) == 2000


def test_workloads_have_three_shapes_and_stable_fingerprint():
    settings = Settings(seed=11, machines=4, job_count=12, case_count=6, candidate_limit=30)
    workloads = generate_workloads(settings)
    assert workloads == generate_workloads(settings)
    assert len(workloads) == 6
    assert all(len(jobs) == 12 and min(jobs) > 0 for jobs in workloads)
    assert workload_fingerprint(4, workloads) == workload_fingerprint(4, workloads)
    assert workload_fingerprint(5, workloads) != workload_fingerprint(4, workloads)

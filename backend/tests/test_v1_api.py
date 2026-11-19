
def test_holdout_manifest_ranking_and_solve(client):
    response = client.post('/api/runs', json={
        'seed': 42, 'machines': 3, 'job_count': 8,
        'case_count': 2, 'holdout_count': 2, 'candidate_limit': 12,
    })
    assert response.status_code == 201, response.text
    run = response.json()
    assert run['holdout_count'] == 2
    assert run['winner_holdout_ratio'] is not None
    assert len(run['holdout_digest']) == 64
    manifest = client.get(f"/api/runs/{run['id']}/manifest").json()
    assert manifest['format_version'] == 'OMEGA2'
    assert len(manifest['holdout_workloads']) == 2
    assert '--holdout-count 2' in manifest['reproduce_command']

    by_holdout = client.get(f"/api/runs/{run['id']}/candidates?sort=holdout").json()
    assert by_holdout['total'] == 12
    assert by_holdout['items'][0]['holdout_average_ratio'] == 1.0
    assert len(by_holdout['items'][0]['train_case_ratios']) == 2
    assert len(by_holdout['items'][0]['holdout_case_ratios']) == 2
    assert client.get(f"/api/runs/{run['id']}/candidates?sort=invalid").status_code == 422

    solve = client.post('/api/solve', json={
        'durations': [9, 8, 7, 6], 'machines': 2, 'candidate_limit': 12,
    })
    assert solve.status_code == 200, solve.text
    result = solve.json()
    assert result['valid_count'] == 11
    assert result['invalid_count'] == 1
    assert len(result['assignments']) == 4
    assert sum(result['machine_loads']) == 30
    assert result['lower_bound'] == 15
    assert result['makespan'] >= 15
    assert result['makespan'] <= result['baseline_makespan']


def test_custom_solver_validation(client):
    for payload in (
        {'durations': [3, -1], 'machines': 3},
        {'durations': [3.1, 4], 'machines': 3},
        {'durations': [True, 4], 'machines': 3},
        {'durations': [2], 'machines': 3},
        {'durations': [2, 4], 'machines': 0},
        {'durations': [2, 4], 'machines': 3, 'candidate_limit': 501},
    ):
        assert client.post('/api/solve', json=payload).status_code == 422
    assert client.post('/api/runs', json={'holdout_count': 99}).status_code == 422

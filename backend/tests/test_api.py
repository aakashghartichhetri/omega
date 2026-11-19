def test_demo_search_can_be_created_filtered_and_reproduced(client):
    response = client.post("/api/runs", json={"seed": 42, "machines": 3, "job_count": 8,
                                               "case_count": 3, "candidate_limit": 12})
    assert response.status_code == 201, response.text
    run = response.json()
    assert run["valid_count"] == 11
    assert run["invalid_count"] == 1
    assert run["winner_ratio"] == 1.0
    run_id = run["id"]

    assert client.get("/api/runs").json()[0]["id"] == run_id
    assert client.get(f"/api/runs/{run_id}").status_code == 200
    all_candidates = client.get(f"/api/runs/{run_id}/candidates?limit=20").json()
    assert all_candidates["total"] == 12
    assert all_candidates["items"][0]["status"] == "valid"
    invalid = client.get(f"/api/runs/{run_id}/candidates?status=invalid").json()
    assert invalid["total"] == 1
    assert "each job" in invalid["items"][0]["reason"]
    assert client.get(f"/api/runs/{run_id}/candidates?query=INVALID").json()["total"] == 1

    manifest = client.get(f"/api/runs/{run_id}/manifest").json()
    assert manifest["workload_digest"] == run["workload_digest"]
    assert len(manifest["workloads"]) == 3
    assert "--seed 42" in manifest["reproduce_command"]


def test_invalid_inputs_and_not_found(client):
    assert client.post("/api/runs", json={"machines": 0}).status_code == 422
    assert client.post("/api/runs", json={"candidate_limit": 4000}).status_code == 422
    assert client.post("/api/runs", json={"seed": "42"}).status_code == 422
    assert client.post("/api/runs", json={"unexpected": True}).status_code == 422
    assert client.get("/api/runs/missing").status_code == 404
    assert client.get("/api/runs/missing/candidates").status_code == 404
    assert client.get("/api/runs/missing/manifest").status_code == 404
    assert client.get("/api/health").json() == {"status": "ok"}


def test_candidate_filters_reject_bad_parameters(client):
    assert client.get("/api/runs/x/candidates?status=deleted").status_code == 422
    assert client.get("/api/runs/x/candidates?limit=1000").status_code == 422

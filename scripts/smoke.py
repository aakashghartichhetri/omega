"""End-to-end smoke test against a running OMEGA deployment, stdlib only.

Use OMEGA_API_URL (default http://localhost:8001) and optional OMEGA_API_KEY.
"""
from __future__ import annotations

import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = os.getenv("OMEGA_API_URL", "http://localhost:8001").rstrip("/")
KEY = os.getenv("OMEGA_API_KEY", "")


def api(path: str, data: dict | None = None) -> dict | list:
    headers = {"Content-Type": "application/json"}
    if KEY:
        headers["X-OMEGA-Key"] = KEY
    body = json.dumps(data).encode() if data is not None else None
    request = Request(BASE + path, data=body, headers=headers,
                      method="POST" if data is not None else "GET")
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def main() -> int:
    health = api("/api/health")
    assert health == {"status": "ok"}, health
    print("[1/4] API healthy")

    created = api("/api/jobs", {
        "seed": 1984, "machines": 3, "job_count": 8,
        "case_count": 2, "holdout_count": 1, "candidate_limit": 12,
    })
    assert isinstance(created, dict)
    job_id = created["id"]
    deadline = time.monotonic() + 120
    while True:
        job = api(f"/api/jobs/{job_id}")
        assert isinstance(job, dict)
        if job["status"] in ("succeeded", "failed", "cancelled"):
            break
        if time.monotonic() >= deadline:
            raise TimeoutError("Experiment did not complete within 120 seconds")
        time.sleep(2)
    assert job["status"] == "succeeded", f"Experiment {job['status']}: {job.get('error')}"
    print("[2/4] Background worker saved experiment")

    run_id = job["run_id"]
    candidates = api(f"/api/runs/{run_id}/candidates?limit=20")
    manifest = api(f"/api/runs/{run_id}/manifest")
    assert isinstance(candidates, dict) and candidates["total"] == 12
    assert isinstance(manifest, dict) and len(manifest["workloads"]) == 2
    assert sum(row["status"] == "invalid" for row in candidates["items"]) == 1
    assert manifest["holdout_digest"]
    print("[3/4] Results and manifest verified (12 recipes, 1 canary)")

    solved = api("/api/solve", {"durations": [9, 8, 7, 6], "machines": 2, "candidate_limit": 12})
    assert isinstance(solved, dict) and solved["makespan"] >= solved["lower_bound"]
    assert solved["makespan"] <= solved["baseline_makespan"]
    print("[4/4] Custom-job solver produced verified schedule")
    print(f"PASS | saved run {run_id} | {BASE}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (HTTPError, URLError, AssertionError, TimeoutError, KeyError, ValueError) as exc:
        print(f"FAIL | {exc}", file=sys.stderr)
        sys.exit(1)

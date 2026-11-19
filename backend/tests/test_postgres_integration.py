"""Real PostgreSQL/Rust smoke test, explicitly enabled in CI."""
import os

import pytest


@pytest.mark.skipif(os.environ.get("OMEGA_TEST_POSTGRES") != "1", reason="needs CI PostgreSQL")
def test_real_postgres_engine_migration_and_api_roundtrip():
    from fastapi.testclient import TestClient
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.main import app
    from app.models import Run

    with TestClient(app) as client:
        response = client.post("/api/runs", json={
            "seed": 77, "machines": 3, "job_count": 8, "case_count": 3,
            "holdout_count": 2, "candidate_limit": 12,
        })
        assert response.status_code == 201, response.text
        run = response.json()
        assert run["valid_count"] == 11
        assert run["invalid_count"] == 1
        assert run["winner_holdout_ratio"] is not None
        assert client.get(f"/api/runs/{run['id']}/manifest").status_code == 200
        assert client.get(f"/api/runs/{run['id']}/candidates").json()["total"] == 12
        with SessionLocal() as db:
            assert db.scalar(select(Run.id).where(Run.id == run["id"])) == run["id"]
            db.delete(db.get(Run, run["id"]))
            db.commit()

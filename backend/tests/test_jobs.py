"""Queue behavior, HTTP contract, cancellation, and atomic persistence."""
import os
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.jobs import enqueue, cancel
from app.models import SearchJob, Run
from app.schemas import RunRequest
from app import search, worker


def test_jobs_api_queues_and_cancels(client):
    response = client.post("/api/jobs", json={"seed": 7, "machines": 3, "job_count": 8,
                                               "case_count": 2, "holdout_count": 1, "candidate_limit": 10})
    assert response.status_code == 202, response.text
    job = response.json()
    assert job["status"] == "queued"
    assert job["progress"] == 0
    assert job["parameters"]["seed"] == 7
    assert client.get("/api/jobs").json()[0]["id"] == job["id"]
    assert client.get(f"/api/jobs/{job['id']}").status_code == 200
    cancelled = client.post(f"/api/jobs/{job['id']}/cancel").json()
    assert cancelled["status"] == "cancelled"
    assert client.post(f"/api/jobs/{job['id']}/cancel").json()["status"] == "cancelled"
    assert client.get("/api/jobs/no-such-job").status_code == 404
    assert client.post("/api/jobs/no-such-job/cancel").status_code == 404
    assert client.post("/api/jobs", json={"machines": 0}).status_code == 422


def test_worker_finishes_and_saves_run(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'jobs.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        job = enqueue(db, RunRequest(machines=3, job_count=8, case_count=3,
                                     holdout_count=2, candidate_limit=15))
        job_id = job.id
    assert worker.claim_next(factory) == job_id
    assert worker.claim_next(factory) is None

    def fake_rust(machines, workloads, recipes):
        output = {}
        for index, recipe in enumerate(recipes):
            for case_index, jobs in enumerate(workloads):
                loads = [0] * machines
                assignments = []
                for duration in jobs:
                    machine = min(range(machines), key=lambda i: (loads[i], i))
                    assignments.append(machine)
                    loads[machine] += duration
                if recipe.canary:
                    assignments.append(0)
                output[(index, case_index)] = assignments
        return output
    monkeypatch.setattr(search, "run_rust_engine", fake_rust)
    worker.process_job(job_id, factory)
    with factory() as db:
        finished = db.get(SearchJob, job_id)
        assert finished.status == "succeeded"
        assert finished.progress == 100
        assert finished.run_id is not None
        run = db.get(Run, finished.run_id)
        assert run.valid_count == 14
        assert run.invalid_count == 1
        assert len(run.candidates) == 15
        assert len(run.holdout_workloads) == 2
    engine.dispose()


def test_worker_honors_queued_and_running_cancellation(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'cancel.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        first = enqueue(db, RunRequest(candidate_limit=12))
        first_id = first.id
        cancel(db, first)
        second = enqueue(db, RunRequest(candidate_limit=10))
        second_id = second.id
    assert worker.claim_next(factory) == second_id

    def cancelled(*_args, **_kwargs):
        with factory() as db:
            row = db.get(SearchJob, second_id)
            row.cancel_requested = True
            db.commit()
        # Stop after the next check (as if the Rust batch had just finished).
        _kwargs["progress"](30)
        raise AssertionError("Must not continue after cancellation")
    monkeypatch.setattr(worker, "evaluate", cancelled)
    worker.process_job(second_id, factory)
    with factory() as db:
        assert db.get(SearchJob, first_id).status == "cancelled"
        assert db.get(SearchJob, second_id).status == "cancelled"
        assert db.scalar(select(Run.id)) is None
    engine.dispose()


def test_interrupted_worker_is_reported_as_failed(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'failure.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        job = enqueue(db, RunRequest())
        job_id = job.id
    worker.claim_next(factory)
    worker.recover_interrupted(factory)
    with factory() as db:
        row = db.get(SearchJob, job_id)
        assert row.status == "failed"
        assert "Worker stopped" in row.error
    engine.dispose()


def test_api_key_is_optional_locally_but_enforced_when_set(client, monkeypatch):
    monkeypatch.setenv("OMEGA_API_KEY", "test-secret")
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/runs").status_code == 401
    assert client.post("/api/jobs", json={}).status_code == 401
    assert client.get("/api/runs", headers={"X-OMEGA-Key": "wrong"}).status_code == 401
    assert client.get("/api/runs", headers={"X-OMEGA-Key": "test-secret"}).status_code == 200

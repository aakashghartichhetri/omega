"""Real PostgreSQL durable job and Rust engine integration test, CI only."""
import os

import pytest


@pytest.mark.skipif(os.environ.get("OMEGA_TEST_POSTGRES") != "1", reason="needs CI PostgreSQL")
def test_postgres_worker_processes_real_rust_job():
    from app.db import SessionLocal
    from app.jobs import enqueue
    from app.models import Run, SearchJob
    from app.schemas import RunRequest
    from app.worker import claim_next, process_job

    with SessionLocal() as db:
        job_id = enqueue(db, RunRequest(seed=77, machines=3, job_count=8,
                                        case_count=2, holdout_count=1, candidate_limit=12)).id

    try:
        assert claim_next() == job_id
        process_job(job_id)
        with SessionLocal() as db:
            row = db.get(SearchJob, job_id)
            assert row.status == "succeeded", row.error
            assert row.progress == 100
            result = db.get(Run, row.run_id)
            assert result.valid_count == 11
            assert result.invalid_count == 1
            assert result.holdout_count == 1
    finally:
        with SessionLocal() as db:
            row = db.get(SearchJob, job_id)
            if row is not None:
                if row.run_id:
                    saved = db.get(Run, row.run_id)
                    if saved:
                        db.delete(saved)
                db.delete(row)
                db.commit()

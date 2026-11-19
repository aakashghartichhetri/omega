"""Single-worker durable search queue; run with `python -m app.worker`.

Use a single worker replica. A crashed in-flight job is marked failed at boot;
queued work remains durable and is processed after restart.
"""
from __future__ import annotations

import logging
import signal
import time

from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from .db import SessionLocal
from .models import SearchJob
from .schemas import RunRequest
from .search import Settings, evaluate
from .service import save_evaluation
from .jobs import utc_now

logger = logging.getLogger("omega.worker")


class CancelledSearch(Exception):
    pass


def recover_interrupted(factory: sessionmaker = SessionLocal) -> None:
    with factory() as db:
        db.execute(update(SearchJob).where(SearchJob.status == "running").values(
            status="failed", finished_at=utc_now(),
            error="Worker stopped before completion. Retry by creating a new experiment.",
        ))
        db.commit()


def claim_next(factory: sessionmaker = SessionLocal) -> str | None:
    with factory() as db:
        # SKIP LOCKED prevents two claimers from taking the same row on PostgreSQL.
        job = db.scalar(select(SearchJob).where(SearchJob.status == "queued")
                        .order_by(SearchJob.created_at, SearchJob.id)
                        .with_for_update(skip_locked=True).limit(1))
        if job is None:
            return None
        job.status = "running"
        job.started_at = utc_now()
        job.progress = 1
        job.error = None
        db.commit()
        return job.id


def process_job(job_id: str, factory: sessionmaker = SessionLocal) -> None:
    with factory() as db:
        job = db.get(SearchJob, job_id)
        if job is None or job.status != "running":
            return
        parameters = dict(job.parameters)

    def report(percent: int) -> None:
        with factory() as db:
            job = db.get(SearchJob, job_id)
            if job is None or job.cancel_requested:
                raise CancelledSearch()
            job.progress = percent
            db.commit()

    try:
        report(2)
        evaluation = evaluate(Settings(**RunRequest.model_validate(parameters).model_dump()), progress=report)
        with factory() as db:
            # Lock prevents a cancellation request from racing the final commit.
            job = db.scalar(select(SearchJob).where(SearchJob.id == job_id).with_for_update())
            if job is None or job.status != "running":
                return
            if job.cancel_requested:
                job.status = "cancelled"
            else:
                # Save run + mark completed in one transaction: no half-written results.
                saved = save_evaluation(db, evaluation, commit=False)
                job.run_id = saved.id
                job.status = "succeeded"
                job.progress = 100
            job.finished_at = utc_now()
            db.commit()
    except CancelledSearch:
        with factory() as db:
            job = db.get(SearchJob, job_id)
            if job and job.status == "running":
                job.status = "cancelled"
                job.finished_at = utc_now()
                db.commit()
    except Exception as exc:
        logger.exception("Experiment %s failed", job_id)
        with factory() as db:
            job = db.get(SearchJob, job_id)
            if job and job.status == "running":
                job.status = "failed"
                # Errors are logged; avoid exposing server internals to browser clients.
                job.error = "Experiment failed. Check worker logs for details."
                job.finished_at = utc_now()
                db.commit()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stop = False

    def request_stop(_signum, _frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    recover_interrupted()
    logger.info("OMEGA worker ready")
    while not stop:
        job_id = claim_next()
        if job_id:
            logger.info("Processing experiment %s", job_id)
            process_job(job_id)
        else:
            time.sleep(1)
    logger.info("Worker stopped")


if __name__ == "__main__":
    main()

"""A deliberately small, PostgreSQL-backed queue for one bounded worker.

The API never runs the expensive search. A separate process claims a row,
executes the Rust engine, and atomically saves the completed experiment.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .models import SearchJob
from .schemas import RunRequest


class QueueFull(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue(db: Session, settings: RunRequest) -> SearchJob:
    # Serialize admission across API workers so concurrent requests cannot bypass the bound.
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(20261118)"))
    pending = db.scalar(select(func.count(SearchJob.id)).where(
        SearchJob.status.in_(("queued", "running")))) or 0
    if pending >= 10:
        raise QueueFull("The experiment queue is full (10 pending/running). Try again later.")
    job = SearchJob(
        id=str(uuid4()), created_at=utc_now(), status="queued", progress=0,
        parameters=settings.model_dump(), cancel_requested=False,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def cancel(db: Session, job: SearchJob) -> SearchJob:
    # Queued jobs can be cancelled immediately; running jobs stop at the next batch boundary.
    if job.status == "queued":
        job.status = "cancelled"
        job.finished_at = utc_now()
    elif job.status == "running":
        job.cancel_requested = True
    db.commit()
    db.refresh(job)
    return job

from fastapi import Depends, FastAPI, HTTPException, Query, Security
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from fastapi.security import APIKeyHeader
import hmac
import os

from .db import get_db
from .engine import EngineError
from .models import Candidate, Run, SearchJob
from .schemas import CandidatePage, RunRequest, RunSummary, SolveRequest, SolveResponse, JobSummary
from .search import Settings, solve_jobs
from .service import create_run
from .jobs import QueueFull, enqueue, cancel
from .verification import InvalidSchedule

app = FastAPI(title="OMEGA — The Invention Machine", version="2.0.0",
              description="Search deterministic scheduling heuristics and independently verify their makespans.")


api_key_header = APIKeyHeader(name="X-OMEGA-Key", auto_error=False)


def require_key(token: str | None = Security(api_key_header)) -> None:
    secret = os.environ.get("OMEGA_API_KEY", "")
    if secret and not hmac.compare_digest(token or "", secret):
        raise HTTPException(status_code=401, detail="Valid X-OMEGA-Key header required")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/runs", response_model=RunSummary, status_code=201, dependencies=[Depends(require_key)])
def start_run(request: RunRequest, db: Session = Depends(get_db)):
    try:
        return create_run(db, Settings(**request.model_dump()))
    except (EngineError, InvalidSchedule) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/solve", response_model=SolveResponse, dependencies=[Depends(require_key)])
def solve(request: SolveRequest):
    """One-off scheduling problem; results are not saved as experiments."""
    try:
        return solve_jobs(request.durations, request.machines, request.candidate_limit)
    except (EngineError, InvalidSchedule) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/runs", response_model=list[RunSummary], dependencies=[Depends(require_key)])
def list_runs(db: Session = Depends(get_db)):
    return db.scalars(select(Run).order_by(Run.created_at.desc()).limit(10)).all()


def find_run(db: Session, run_id: str) -> Run:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@app.get("/api/runs/{run_id}", response_model=RunSummary, dependencies=[Depends(require_key)])
def get_run(run_id: str, db: Session = Depends(get_db)):
    return find_run(db, run_id)


@app.get("/api/runs/{run_id}/candidates", response_model=CandidatePage, dependencies=[Depends(require_key)])
def list_candidates(
    run_id: str,
    status: str = Query("all", pattern="^(all|valid|invalid)$"),
    query: str = Query("", max_length=80),
    sort: str = Query("train", pattern="^(train|holdout)$"),
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
    db: Session = Depends(get_db),
):
    find_run(db, run_id)
    statement = select(Candidate).where(Candidate.run_id == run_id)
    if status != "all":
        statement = statement.where(Candidate.status == status)
    if query.strip():
        # SQLAlchemy binds this value rather than concatenating it into SQL.
        escaped = query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        statement = statement.where(Candidate.name.ilike(f"%{escaped}%", escape="\\"))
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    # Valid scores first, ordered by quality; invalid canaries are visible last.
    score_column = Candidate.holdout_average_ratio if sort == "holdout" else Candidate.average_ratio
    statement = statement.order_by(score_column.is_(None), score_column, Candidate.ordinal)
    return CandidatePage(total=total, items=db.scalars(statement.offset(offset).limit(limit)).all())


@app.get("/api/runs/{run_id}/manifest", dependencies=[Depends(require_key)])
def manifest(run_id: str, db: Session = Depends(get_db)):
    run = find_run(db, run_id)
    winner = db.scalar(select(Candidate).where(Candidate.run_id == run_id,
                                                Candidate.ordinal == run.winner_ordinal))
    return {
        "format_version": "OMEGA2" if run.holdout_count else "OMEGA1",
        "parameters": {"seed": run.seed, "machines": run.machines, "job_count": run.job_count,
                       "case_count": run.case_count, "holdout_count": run.holdout_count,
                       "candidate_limit": run.candidate_limit},
        "workload_digest": run.workload_digest,
        "workloads": run.workloads,
        "holdout_digest": run.holdout_digest,
        "holdout_workloads": run.holdout_workloads or [],
        "baseline": "longest + least_loaded + 0 improvement passes",
        "winner": {"ordinal": winner.ordinal, "name": winner.name,
                   "average_ratio": winner.average_ratio,
                   "holdout_average_ratio": winner.holdout_average_ratio},
        "reproduce_command": (
            "python -m app.benchmark "
            f"--seed {run.seed} --machines {run.machines} --job-count {run.job_count} "
            f"--case-count {run.case_count} --holdout-count {run.holdout_count} "
            f"--candidates {run.candidate_limit}"
        ),
        "note": "Only training cases select the winner; unseen holdout cases report generalization. "
                "Ratios measure makespan, not computation time. The rejected canary is intentional.",
    }


@app.post("/api/jobs", response_model=JobSummary, status_code=202, dependencies=[Depends(require_key)])
def queue_experiment(request: RunRequest, db: Session = Depends(get_db)):
    try:
        return enqueue(db, request)
    except QueueFull as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc


@app.get("/api/jobs", response_model=list[JobSummary], dependencies=[Depends(require_key)])
def list_jobs(db: Session = Depends(get_db)):
    return db.scalars(select(SearchJob).order_by(SearchJob.created_at.desc()).limit(30)).all()


def find_job(db: Session, job_id: str) -> SearchJob:
    job = db.get(SearchJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Experiment job not found")
    return job


@app.get("/api/jobs/{job_id}", response_model=JobSummary, dependencies=[Depends(require_key)])
def get_job(job_id: str, db: Session = Depends(get_db)):
    return find_job(db, job_id)


@app.post("/api/jobs/{job_id}/cancel", response_model=JobSummary, dependencies=[Depends(require_key)])
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    # Use a row lock so cancellation is serialized against worker completion.
    job = db.scalar(select(SearchJob).where(SearchJob.id == job_id).with_for_update())
    if job is None:
        raise HTTPException(status_code=404, detail="Experiment job not found")
    return cancel(db, job)

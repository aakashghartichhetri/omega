from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    seed: Mapped[int] = mapped_column(Integer)
    machines: Mapped[int] = mapped_column(Integer)
    job_count: Mapped[int] = mapped_column(Integer)
    case_count: Mapped[int] = mapped_column(Integer)
    holdout_count: Mapped[int] = mapped_column(Integer, default=0)
    holdout_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    holdout_workloads: Mapped[list | None] = mapped_column(JSON, nullable=True)
    winner_holdout_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    candidate_limit: Mapped[int] = mapped_column(Integer)
    workload_digest: Mapped[str] = mapped_column(String(64))
    workloads: Mapped[list] = mapped_column(JSON)
    winner_ordinal: Mapped[int] = mapped_column(Integer)
    winner_ratio: Mapped[float] = mapped_column(Float)
    valid_count: Mapped[int] = mapped_column(Integer)
    invalid_count: Mapped[int] = mapped_column(Integer)
    candidates: Mapped[list["Candidate"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(180))
    ordering: Mapped[str] = mapped_column(String(24))
    order_parameter: Mapped[int] = mapped_column(Integer)
    placement: Mapped[str] = mapped_column(String(24))
    placement_seed: Mapped[int] = mapped_column(Integer)
    passes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    average_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    worst_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_makespan: Mapped[float | None] = mapped_column(Float, nullable=True)
    preview_assignments: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    preview_makespan: Mapped[int | None] = mapped_column(Integer, nullable=True)
    train_case_ratios: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    holdout_case_ratios: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    holdout_average_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    holdout_worst_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    run: Mapped[Run] = relationship(back_populates="candidates")


class SearchJob(Base):
    """Durable work queue: one worker owns the finite scheduling search."""
    __tablename__ = "search_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), index=True, default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    parameters: Mapped[dict] = mapped_column(JSON)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("runs.id", ondelete="SET NULL"), nullable=True)

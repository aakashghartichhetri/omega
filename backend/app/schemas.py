from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seed: int = Field(default=42, ge=0, le=2_147_483_647, strict=True)
    machines: int = Field(default=4, ge=2, le=12, strict=True)
    job_count: int = Field(default=24, ge=4, le=60, strict=True)
    case_count: int = Field(default=8, ge=2, le=12, strict=True)
    holdout_count: int = Field(default=4, ge=0, le=12, strict=True)
    candidate_limit: int = Field(default=500, ge=2, le=2000, strict=True)


class RunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    seed: int
    machines: int
    job_count: int
    case_count: int
    holdout_count: int
    candidate_limit: int
    workload_digest: str
    holdout_digest: str | None
    winner_ordinal: int
    winner_ratio: float
    winner_holdout_ratio: float | None
    valid_count: int
    invalid_count: int


class CandidateSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ordinal: int
    name: str
    ordering: str
    order_parameter: int
    placement: str
    placement_seed: int
    passes: int
    status: str
    reason: str | None
    average_ratio: float | None
    worst_ratio: float | None
    mean_makespan: float | None
    preview_assignments: list[int] | None
    preview_makespan: int | None
    train_case_ratios: list[float] | None
    holdout_case_ratios: list[float] | None
    holdout_average_ratio: float | None
    holdout_worst_ratio: float | None


class CandidatePage(BaseModel):
    total: int
    items: list[CandidateSummary]


class SolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    machines: int = Field(default=3, ge=2, le=12, strict=True)
    durations: list[StrictInt] = Field(min_length=2, max_length=60)
    candidate_limit: int = Field(default=100, ge=2, le=500, strict=True)

    @field_validator("durations")
    @classmethod
    def _valid_durations(cls, values: list[int]) -> list[int]:
        if any(value <= 0 or value > 1_000_000 for value in values):
            raise ValueError("each duration must be from 1 to 1,000,000")
        return values


class SolveResponse(BaseModel):
    winner_ordinal: int
    winner_name: str
    assignments: list[int]
    machine_loads: list[int]
    makespan: int
    baseline_makespan: int
    lower_bound: int
    valid_count: int
    invalid_count: int


class JobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    status: str
    progress: int
    parameters: RunRequest
    cancel_requested: bool
    error: str | None
    run_id: str | None

from uuid import uuid4

from sqlalchemy.orm import Session

from .models import Candidate, Run
from .search import Evaluation, Settings, evaluate


def save_evaluation(db: Session, evaluation: Evaluation, *, commit: bool = True) -> Run:
    settings = evaluation.settings
    run = Run(
        id=str(uuid4()), seed=settings.seed, machines=settings.machines,
        job_count=settings.job_count, case_count=settings.case_count,
        candidate_limit=settings.candidate_limit, workload_digest=evaluation.workload_digest,
        holdout_count=settings.holdout_count, holdout_digest=evaluation.holdout_digest,
        holdout_workloads=evaluation.holdout_workloads,
        winner_holdout_ratio=evaluation.winner.holdout_average_ratio,
        workloads=evaluation.workloads, winner_ordinal=evaluation.winner.ordinal,
        winner_ratio=evaluation.winner.average_ratio,
        valid_count=sum(candidate.status == "valid" for candidate in evaluation.candidates),
        invalid_count=sum(candidate.status == "invalid" for candidate in evaluation.candidates),
    )
    run.candidates = [Candidate(
        ordinal=score.ordinal, name=score.recipe.name,
        ordering=score.recipe.ordering, order_parameter=score.recipe.order_parameter,
        placement=score.recipe.placement, placement_seed=score.recipe.placement_seed,
        passes=score.recipe.passes, status=score.status, reason=score.reason,
        average_ratio=score.average_ratio, worst_ratio=score.worst_ratio,
        mean_makespan=score.mean_makespan, preview_assignments=score.preview_assignments,
        preview_makespan=score.preview_makespan,
        train_case_ratios=score.train_case_ratios, holdout_case_ratios=score.holdout_case_ratios,
        holdout_average_ratio=score.holdout_average_ratio, holdout_worst_ratio=score.holdout_worst_ratio,
    ) for score in evaluation.candidates]
    db.add(run)
    db.flush()
    if commit:
        db.commit()
        db.refresh(run)
    return run


def create_run(db: Session, settings: Settings) -> Run:
    # Compute before beginning the write so an engine failure leaves no partial run.
    evaluation = evaluate(settings)
    return save_evaluation(db, evaluation)

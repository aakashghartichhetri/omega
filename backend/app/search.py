"""Deterministic workload generation and exploration of a finite heuristic space."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from itertools import product
import json
import random
from typing import Callable

from .engine import run_rust_engine
from .verification import InvalidSchedule, verify_schedule


@dataclass(frozen=True)
class Settings:
    seed: int = 42
    machines: int = 4
    job_count: int = 24
    case_count: int = 8
    candidate_limit: int = 500
    holdout_count: int = 4


@dataclass(frozen=True)
class Recipe:
    ordering: str
    order_parameter: int
    placement: str
    placement_seed: int
    passes: int
    canary: bool = False

    @property
    def name(self) -> str:
        if self.canary:
            return "INVALID CANARY (verifier demonstration)"
        order = self.ordering + (f"({self.order_parameter})" if self.ordering in ("shuffled", "windowed") else "")
        placement = self.placement + (f"({self.placement_seed})" if self.placement == "power_of_two" else "")
        return f"{order} + {placement} + {self.passes} improvement passes"


@dataclass
class CandidateScore:
    ordinal: int
    recipe: Recipe
    status: str
    reason: str | None = None
    average_ratio: float | None = None
    worst_ratio: float | None = None
    mean_makespan: float | None = None
    preview_assignments: list[int] | None = None
    preview_makespan: int | None = None
    train_case_ratios: list[float] | None = None
    holdout_case_ratios: list[float] | None = None
    holdout_average_ratio: float | None = None
    holdout_worst_ratio: float | None = None


@dataclass
class Evaluation:
    settings: Settings
    workloads: list[list[int]]
    workload_digest: str
    candidates: list[CandidateScore]
    winner: CandidateScore
    baseline: CandidateScore
    holdout_workloads: list[list[int]]
    holdout_digest: str | None


def generate_workloads(settings: Settings) -> list[list[int]]:
    """Three workload shapes reduce the chance of winning on one artificial case."""
    randomizer = random.Random(settings.seed)
    workloads = []
    for case_index in range(settings.case_count):
        shape = case_index % 3
        if shape == 0:
            jobs = [randomizer.randint(5, 75) for _ in range(settings.job_count)]
        elif shape == 1:
            jobs = [randomizer.randint(3, 14) if randomizer.random() < 0.65
                    else randomizer.randint(55, 100) for _ in range(settings.job_count)]
        else:
            jobs = [randomizer.randint(65, 110) if i % 7 == 0
                    else randomizer.randint(1, 35) for i in range(settings.job_count)]
            randomizer.shuffle(jobs)
        workloads.append(jobs)
    return workloads


def workload_fingerprint(machines: int, workloads: list[list[int]]) -> str:
    payload = json.dumps({"machines": machines, "workloads": workloads}, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def generate_recipes(limit: int) -> list[Recipe]:
    baseline = Recipe("longest", 0, "least_loaded", 0, 0)
    canary = Recipe("longest", 0, "least_loaded", 0, 0, canary=True)
    orders = [("longest", 0), ("shortest", 0), ("zigzag", 0)]
    orders += [("windowed", size) for size in (2, 3, 4, 5, 6, 8, 10)]
    orders += [("shuffled", seed) for seed in range(40)]
    placements = [("least_loaded", 0), ("round_robin", 0), ("second_least", 0)]
    placements += [("power_of_two", seed) for seed in range(10)]
    options = [Recipe(order, order_arg, placement, place_seed, passes)
               for (order, order_arg), (placement, place_seed), passes in product(orders, placements, range(4))]
    # Fixed mixing makes a small search sample diverse and keeps its results reproducible.
    random.Random(901).shuffle(options)
    recipes = [baseline, canary]
    recipes.extend(recipe for recipe in options if recipe != baseline)
    return recipes[:limit]


def generate_holdout_workloads(settings: Settings) -> list[list[int]]:
    """A separate random stream prevents choosing a winner on its test cases."""
    if settings.holdout_count == 0:
        return []
    unseen = Settings(
        seed=(settings.seed + 1_000_003) % 2_147_483_648,
        machines=settings.machines,
        job_count=settings.job_count,
        case_count=settings.holdout_count,
        candidate_limit=settings.candidate_limit,
        holdout_count=0,
    )
    return generate_workloads(unseen)


def evaluate(settings: Settings, progress: Callable[[int], None] | None = None) -> Evaluation:
    """Rank on training cases only; report holdout results without re-ranking."""
    workloads = generate_workloads(settings)
    holdout_workloads = generate_holdout_workloads(settings)
    all_workloads = workloads + holdout_workloads
    recipes = generate_recipes(settings.candidate_limit)
    if progress is None:
        outputs = run_rust_engine(settings.machines, all_workloads, recipes)
    else:
        outputs: dict[tuple[int, int], list[int]] = {}
        # Smaller batches bound subprocess output and allow cancellation between batches.
        for start in range(0, len(recipes), 100):
            batch = recipes[start:start + 100]
            produced = run_rust_engine(settings.machines, all_workloads, batch)
            for (local_ordinal, case_index), assignment in produced.items():
                outputs[(start + local_ordinal, case_index)] = assignment
            progress(min(95, round(95 * (start + len(batch)) / len(recipes))))

    baseline_makespans = []
    for index, jobs in enumerate(all_workloads):
        assignment = outputs.get((0, index))
        if assignment is None:
            raise InvalidSchedule("baseline engine output is missing")
        baseline_makespans.append(verify_schedule(jobs, assignment, settings.machines))

    scores: list[CandidateScore] = []
    for ordinal, recipe in enumerate(recipes):
        makespans = []
        preview = None
        try:
            for case_index, jobs in enumerate(all_workloads):
                if (ordinal, case_index) not in outputs:
                    raise InvalidSchedule("engine omitted an assignment")
                assignments = outputs[(ordinal, case_index)]
                makespans.append(verify_schedule(jobs, assignments, settings.machines))
                if case_index == 0:
                    preview = assignments
        except InvalidSchedule as exc:
            scores.append(CandidateScore(ordinal, recipe, "invalid", reason=str(exc)))
            continue

        ratios = [result / baseline for result, baseline in zip(makespans, baseline_makespans)]
        train_ratios = ratios[:len(workloads)]
        holdout_ratios = ratios[len(workloads):]
        scores.append(CandidateScore(
            ordinal=ordinal, recipe=recipe, status="valid",
            average_ratio=sum(train_ratios) / len(train_ratios),
            worst_ratio=max(train_ratios),
            mean_makespan=sum(makespans[:len(workloads)]) / len(workloads),
            preview_assignments=preview, preview_makespan=makespans[0],
            train_case_ratios=train_ratios, holdout_case_ratios=holdout_ratios,
            holdout_average_ratio=(sum(holdout_ratios) / len(holdout_ratios) if holdout_ratios else None),
            holdout_worst_ratio=(max(holdout_ratios) if holdout_ratios else None),
        ))

    valid = [candidate for candidate in scores if candidate.status == "valid"]
    winner = min(valid, key=lambda score: (score.average_ratio, score.worst_ratio, score.ordinal))
    return Evaluation(
        settings, workloads, workload_fingerprint(settings.machines, workloads),
        scores, winner, scores[0], holdout_workloads,
        workload_fingerprint(settings.machines, holdout_workloads) if holdout_workloads else None,
    )


def solve_jobs(durations: list[int], machines: int, candidate_limit: int) -> dict:
    """One-off real input; verify every Rust result and return a usable assignment."""
    recipes = generate_recipes(candidate_limit)
    outputs = run_rust_engine(machines, [durations], recipes)
    valid_count = 0
    rejected_count = 0
    winner: tuple[int, Recipe, list[int], int] | None = None
    baseline_assignment = outputs.get((0, 0))
    if baseline_assignment is None:
        raise InvalidSchedule("baseline engine output is missing")
    baseline_makespan = verify_schedule(durations, baseline_assignment, machines)

    for ordinal, recipe in enumerate(recipes):
        try:
            assignment = outputs.get((ordinal, 0))
            if assignment is None:
                raise InvalidSchedule("engine omitted an assignment")
            makespan = verify_schedule(durations, assignment, machines)
        except InvalidSchedule:
            rejected_count += 1
            continue
        valid_count += 1
        if winner is None or (makespan, ordinal) < (winner[3], winner[0]):
            winner = (ordinal, recipe, assignment, makespan)

    assert winner is not None  # The verified baseline is always one of the recipes.
    ordinal, recipe, assignment, makespan = winner
    loads = [0] * machines
    for job, machine in zip(durations, assignment):
        loads[machine] += job
    return {
        "winner_ordinal": ordinal,
        "winner_name": recipe.name,
        "assignments": assignment,
        "machine_loads": loads,
        "makespan": makespan,
        "baseline_makespan": baseline_makespan,
        "lower_bound": max(max(durations), (sum(durations) + machines - 1) // machines),
        "valid_count": valid_count,
        "invalid_count": rejected_count,
    }

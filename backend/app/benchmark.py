"""Reproduce scoring without a web server or database."""
import argparse
import json

from .search import Settings, evaluate


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce an OMEGA scheduling search")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--machines", type=int, default=4)
    parser.add_argument("--job-count", type=int, default=24)
    parser.add_argument("--case-count", type=int, default=8)
    parser.add_argument("--candidates", type=int, default=500)
    parser.add_argument("--holdout-count", type=int, default=4)
    args = parser.parse_args()
    if not (0 <= args.seed <= 2_147_483_647 and 2 <= args.machines <= 12
            and 4 <= args.job_count <= 60 and 2 <= args.case_count <= 12
            and 2 <= args.candidates <= 2000 and 0 <= args.holdout_count <= 12):
        parser.error("parameters must satisfy the same ranges as the API")
    evaluation = evaluate(Settings(args.seed, args.machines, args.job_count, args.case_count, args.candidates, args.holdout_count))
    ranked = sorted((candidate for candidate in evaluation.candidates if candidate.status == "valid"),
                    key=lambda candidate: (candidate.average_ratio, candidate.worst_ratio, candidate.ordinal))
    print(json.dumps({
        "workload_digest": evaluation.workload_digest,
        "holdout_digest": evaluation.holdout_digest,
        "holdout_case_count": len(evaluation.holdout_workloads),
        "evaluated": len(evaluation.candidates),
        "invalid": sum(item.status == "invalid" for item in evaluation.candidates),
        "baseline_average_ratio": evaluation.baseline.average_ratio,
        "winner": {"ordinal": evaluation.winner.ordinal, "name": evaluation.winner.recipe.name,
                   "average_ratio": evaluation.winner.average_ratio,
                   "holdout_average_ratio": evaluation.winner.holdout_average_ratio},
        "top_5": [{"ordinal": c.ordinal, "name": c.recipe.name, "average_ratio": c.average_ratio,
                   "holdout_average_ratio": c.holdout_average_ratio}
                  for c in ranked[:5]],
    }, indent=2))


if __name__ == "__main__":
    main()

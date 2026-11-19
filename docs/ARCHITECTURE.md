# Architecture and engineering decisions

## Problem definition

Given `n` independent, non-preemptive jobs with positive integer durations and `m` identical machines, assign every job to exactly one machine. Each machine runs its jobs sequentially; the objective is to minimize **makespan** (the maximum total duration assigned to a machine).

For example, durations `[9,8,7,6]` on two machines can produce loads `[15,15]`, which is optimal because total work is 30. This small bounded problem makes verification easy while solution search remains meaningful.

## Search and scientific controls

- **Baseline:** longest-processing-time first (LPT), choosing the current least-loaded machine.
- **Candidate space:** deterministic ordering (longest, shortest, zigzag, windowed, shuffled), machine choice (least-loaded, second-least, round-robin, power-of-two), and up to three strict-improvement move/swap passes.
- **Verifier:** Python checks each assignment's length, machine IDs, and makespan. Candidate-reported scores are never trusted.
- **Metrics:** per-case `candidate makespan / LPT makespan`; average ratio decides the winner on training only, then worst-case ratio and ordinal break ties.
- **Holdout:** independently seeded test cases are evaluated after selection; holdout scores never change the selected winner.
- **Reproducibility:** identical seed, parameters, recipe order, Rust implementation, and workload fingerprints yield identical recorded values. Changes to the algorithm should be versioned.

A deliberate extra-job canary demonstrates rejection. It is a negative-control test, not organically found invalid output.

## Data flow

```text
React (Vite dev / Caddy production)
   |  /api + X-OMEGA-Key (when enabled)
   v
FastAPI -- validates input --> SearchJob row (queued)
                                     |
                                     v
                        Python worker (one replica)
                                     |
                     100-recipe Rust subprocess batches
                                     |
                            independent verifier
                                     |
                         one database transaction
                         /                    \
                  Run + Candidates         Job succeeded
                         |
                      React polls status and reads stored results
```

Run creation uses a bounded input (2–12 machines, 4–60 jobs, 2–12 training cases, 0–12 holdout cases, 2–2000 recipes). The queue admits at most 10 pending/running jobs (serialized with a PostgreSQL advisory transaction lock) and one worker executes at a time. Browser reads are paginated (25 candidates per page).

## Worker lifecycle

`POST /api/jobs` returns HTTP 202 and a durable job ID. The worker locks the oldest queued row and marks it running. It checks cancellation and updates progress between batches. On success, the verified run, its candidates, and the completed job state are committed atomically. Queued jobs survive restarts. If a worker dies while running a job, restart recovery marks it **failed**, with a message to submit again; it never silently claims a partial result is complete.

Cancellation of queued jobs is immediate. Running cancellation is cooperative after the current Rust batch finishes (up to the subprocess timeout). **Only one worker replica is supported**; multi-worker crash recovery, leases, and job reclaiming would need a more sophisticated protocol.

## Storage

- `runs`: input settings, workload fingerprints, stored generated workloads, winning recipe/score.
- `candidates`: verified training/holdout scores, status, rejection reasons, preview assignments.
- `search_jobs`: requested parameters, state, timestamps, progress, cancellation request, resulting run ID.

Alembic migrations `0001`, `0002`, and `0003` extend this schema without deleting earlier experiments.

## Production boundary

Caddy serves the static React production build, proxies same-origin `/api` and `/docs` to the internal FastAPI service, and obtains HTTPS certificates for a real DNS name. The backend and PostgreSQL have **no public host ports** in `compose.deploy.yaml`. A mandatory application API key uses constant-time checking; the browser holds it in volatile memory and adds it as an HTTP header. This is a single-operator shared secret, **not user authentication**.

Future production work: identity and roles, quota/rate limiting, observability, automated PostgreSQL backups, slow-query profiling, structured job leases and horizontal workers, load testing, and staged rollout CI/CD. Do not claim runtime speedups from makespan ratios.

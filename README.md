# OMEGA — Scheduling Lab

A practical project for exploring **how to share jobs across machines**. OMEGA builds and tests scheduling strategies, checks their answers, and shows the results in an interactive dashboard.

**Built with:** Rust · Python · FastAPI · PostgreSQL · React · TypeScript · Docker

## Try it

You need Docker Desktop (or Docker Engine with Compose v2).

```bash
./start.sh
```

The script checks for Docker, creates a local `.env` from the example if needed, builds the containers, and opens the dashboard on macOS. It preserves existing configuration and database volumes. To start without opening a browser, use `./start.sh --no-browser`.

Or run the equivalent Compose commands yourself:

```bash
cp -n .env.example .env
docker compose -p omega up -d --build
docker compose -p omega ps
```

Open **http://localhost:5173** for the app, or **http://localhost:8001/docs** for the API reference.

If an older OMEGA stack is running under the `omega` Compose project name, `./start.sh` updates that project using the new source files. If your previous database has custom credentials, set the same values in `.env` before starting. **Do not use `docker compose down -v`** unless you intentionally want to delete saved PostgreSQL data.

### Things to try

1. **Playground:** Select an example workload or type your own job durations. Change the number of machines, then select **Find a schedule**. Explore both machine load bars and the job-by-job timeline.
2. **Experiments:** Pick **Quick test** to run a short background search. You'll see the job status and progress. You can cancel a running search.
3. **Results:** Select a saved run, search the candidate rankings, compare training and holdout workloads, and inspect individual schedules.
4. **Reproduce:** Download a run's manifest or copy its reproduction command to repeat the experiment.

The interface works on desktop and mobile. The top-right **API docs** link opens the interactive FastAPI reference in a new tab. The bottom-left **Try the playground** shortcut takes you straight to a ready-made example. Experiments remain one click away in the main navigation. API key settings are in the sidebar. The interface follows your device’s light or dark appearance automatically, with input validation, error recovery, and keyboard navigation.

## How it works

```text
React UI → FastAPI → PostgreSQL experiment queue → Python worker
                                                     ↓
                                              Rust scheduler
                                                     ↓
                                           Python verifier
                                                     ↓
                                         PostgreSQL results → React UI
```

The Rust engine searches a **finite set of heuristic recipes**. The Python verifier independently checks the machine assignments and recomputes makespan. OMEGA selects a winner using training workloads, then reports its performance on separate, held-out workloads.

**Makespan** is the time when the busiest machine finishes. A ratio below `1.000` means a shorter schedule than the longest-processing-time-first (LPT) baseline for that test set. It is **not** a measurement of program speed, and it does not prove a globally optimal solution.

## Project structure

```text
backend/              FastAPI routes, verification, worker, migrations, tests
frontend/             Responsive React dashboard and playground
rust-engine/          Scheduling strategies and Rust tests
deploy/               Caddy configuration for HTTPS
scripts/smoke.py      Running-system API → worker → database smoke test
.github/workflows/   CI tests, PostgreSQL integration, image builds
compose.yaml          Local development
compose.deploy.yaml   Single-operator HTTPS deployment
docs/                 Architecture notes
```

## Tests and checks

Run from the project root:

```bash
# Full stack: after starting Compose
python3 scripts/smoke.py

# Frontend production build
cd frontend
npm install --no-audit --no-fund
npm run build
cd ..

# Rust checks (requires Rust)
cargo test --manifest-path rust-engine/Cargo.toml --locked

# Python tests (requires packages in backend/requirements-dev.txt)
cd backend
DATABASE_URL=sqlite+pysqlite:// python -m pytest -q
cd ..
```

The CI workflow also builds the frontend and backend container images, tests Rust and Python, and runs PostgreSQL integration checks.

**Dependency lock:** `frontend/package-lock.json` is not included in this source release because the npm registry was not reachable in the packaging environment. To make installs reproducible, run `cd frontend && npm install --package-lock-only --no-audit --no-fund` on a machine with registry access, commit the generated lockfile, and run the build and GitHub Actions checks before deploying.

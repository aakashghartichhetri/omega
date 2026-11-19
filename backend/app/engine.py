"""Small, documented text protocol between Python and a dependency-free Rust CLI."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .search import Recipe


class EngineError(RuntimeError):
    pass


def engine_path() -> Path:
    default = Path(__file__).resolve().parents[2] / "rust-engine" / "target" / "release" / "omega-engine"
    return Path(os.environ.get("OMEGA_ENGINE_PATH", str(default)))


def run_rust_engine(machines: int, workloads: list[list[int]], recipes: list[Recipe]) -> dict[tuple[int, int], list[int]]:
    lines = [f"OMEGA1|{machines}"]
    lines.extend("W|" + ",".join(map(str, jobs)) for jobs in workloads)
    lines.extend(f"C|{index}|{r.ordering}|{r.order_parameter}|{r.placement}|{r.placement_seed}|{r.passes}|{int(r.canary)}"
                 for index, r in enumerate(recipes))
    lines.append("END")
    try:
        result = subprocess.run([str(engine_path())], input="\n".join(lines) + "\n", text=True,
                                capture_output=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EngineError(f"Rust engine could not run: {exc}") from exc
    if result.returncode:
        raise EngineError(f"Rust engine failed: {result.stderr.strip()[:400]}")

    outputs: dict[tuple[int, int], list[int]] = {}
    for line in result.stdout.splitlines():
        parts = line.split("|")
        if len(parts) != 4 or parts[0] != "S":
            raise EngineError("unrecognized engine response")
        try:
            ordinal, case_index = int(parts[1]), int(parts[2])
            assignment = [int(value) for value in parts[3].split(",")]
        except ValueError as exc:
            raise EngineError("engine returned a non-integer assignment") from exc
        key = (ordinal, case_index)
        if not (0 <= ordinal < len(recipes) and 0 <= case_index < len(workloads)) or key in outputs:
            raise EngineError("engine returned an unexpected or duplicate result")
        outputs[key] = assignment
    return outputs

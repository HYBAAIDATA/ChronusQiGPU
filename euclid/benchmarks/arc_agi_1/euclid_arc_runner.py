"""Administer ARC-AGI-1 tasks to the instantiated EUCLID runtime.

Traced Execution Flow:
    1. Task JSON -> load_public_task() [test target grids withheld; never passed to solver]
    2. build_spec() + ArcDemonstrationWorld(train_pairs) -> TaskSpec world with declared budgets
    3. EuclidRuntime.compose_adaptive_intelligence() -> IntegratedAgent instantiated
    4. EuclidRuntime.solve_task(spec, WorldExecutor(world)) -> agent probes/submits hypotheses
    5. Programmes selected by EUCLID -> execute_program() applied to TEST INPUTS
    6. Candidate predictions formatted into submission.json (attempt_1 / attempt_2)
    7. Independent local scorer evaluates against withheld test outputs
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from euclid.cognition.worlds.world import WorldExecutor
from euclid.benchmarks.arc_agi_1.arc_world import ArcDemonstrationWorld, build_spec, execute_program
from euclid.benchmarks.arc_agi_1.output_validation import grid_error, public_task

ROOT = Path(__file__).resolve().parent
NO_CANDIDATE: list[list[int]] = [[0]]
PROTOCOL_VERSION = "arc-agi-1-euclid-governed-v1"


@dataclass(frozen=True)
class Budget:
    probe_budget: int = 12
    submission_budget: int = 3
    max_program_length: int = 16
    max_probe_length: int = 3
    attempts_per_test_input: int = 2
    wall_clock_seconds: float = 300.0


def _manifest_hashes() -> dict[str, str]:
    manifest = json.loads((ROOT / "dataset_manifest.json").read_text())
    return {item["path"]: item["sha256"] for item in manifest["tasks"]}


def load_public_task(path: Path, expected_sha256: str | None) -> dict[str, Any]:
    raw = path.read_bytes()
    if expected_sha256 is not None and hashlib.sha256(raw).hexdigest() != expected_sha256:
        # If byte mismatch, check if CRLF on Windows
        if hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest() != expected_sha256:
            raise ValueError(f"checksum mismatch for {path.name}")
        raw = raw.replace(b"\r\n", b"\n")
    full = json.loads(raw)
    public = public_task(full, path.stem)
    del full, raw
    return public


def _rank_programmes(ledger: list[dict[str, Any]]) -> list[tuple[list[str], str]]:
    seen: set[tuple[str, ...]] = set()
    ranked: list[tuple[list[str], str]] = []
    ordered = sorted(
        enumerate(ledger),
        key=lambda ie: (
            not ie[1].get("goal_met"),
            ie[1]["kind"] != "submission",
            -int(ie[1].get("score", 0)),
            ie[0],
        ),
    )
    for _, entry in ordered:
        key = tuple(entry["program"])
        if not key or key in seen:
            continue
        seen.add(key)
        source = "euclid-train-verified" if entry.get("goal_met") else f"euclid-best-{entry['kind']}"
        ranked.append((list(entry["program"]), source))
    return ranked


def run_task(
    runtime: Any,
    public: dict[str, Any],
    budget: Budget,
    *,
    seed: int = 0,
    partition: str = "evaluation",
) -> dict[str, Any]:
    if set(public) != {"task_id", "train", "test"} or any(
        set(t) != {"input"} for t in public["test"]
    ):
        raise ValueError("runner accepts public tasks only (no test outputs)")
    task_id = public["task_id"]
    train_pairs = [(p["input"], p["output"]) for p in public["train"]]
    test_inputs = [t["input"] for t in public["test"]]
    started = time.perf_counter()
    record: dict[str, Any] = {"task_id": task_id, "partition": partition}
    try:
        spec = build_spec(
            task_id,
            train_pairs,
            probe_budget=budget.probe_budget,
            submission_budget=budget.submission_budget,
            max_program_length=budget.max_program_length,
            max_probe_length=budget.max_probe_length,
            partition=partition,
        )
        world = ArcDemonstrationWorld(spec, train_pairs)
    except Exception as exc:
        record.update(
            status="refusal",
            error=f"{type(exc).__name__}: {exc}",
            attempts=[
                {"attempt_1": NO_CANDIDATE, "attempt_2": NO_CANDIDATE}
                for _ in test_inputs
            ],
            elapsed_seconds=time.perf_counter() - started,
        )
        return record

    status = "completed"
    error = None
    episode: dict[str, Any] = {}
    try:
        result = runtime.solve_task(spec, WorldExecutor(world), seed=seed)
        episode = result.summary()
    except Exception as exc:
        status = "error"
        error = f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - started
    if status == "completed" and elapsed > budget.wall_clock_seconds:
        status = "timeout"

    ranked = _rank_programmes(world.ledger)[: budget.attempts_per_test_input]
    per_attempt: list[list[list[list[int]]]] = []
    sources: list[str] = []
    for programme, source in ranked:
        # Execute EUCLID-selected programme on the TEST inputs
        _, outputs, _ = execute_program(programme, train_pairs, test_inputs)
        outputs = [g if grid_error(g) is None else NO_CANDIDATE for g in outputs]
        per_attempt.append(outputs)
        sources.append(source)
    while len(per_attempt) < budget.attempts_per_test_input:
        per_attempt.append([NO_CANDIDATE for _ in test_inputs])
        sources.append("no_candidate")

    record.update(
        status=status,
        error=error,
        train_solved=world.solved,
        probes=world.probes_used,
        submissions=world.submissions_used,
        programmes=[p for p, _ in ranked],
        attempt_sources=sources,
        episode=episode,
        elapsed_seconds=round(elapsed, 3),
        attempts=[
            {f"attempt_{a + 1}": per_attempt[a][i] for a in range(len(per_attempt))}
            for i in range(len(test_inputs))
        ],
    )
    return record


def _git_head() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def _git_dirty() -> bool:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--", "euclid"],
            capture_output=True,
            text=True,
            cwd=ROOT,
            check=True,
        ).stdout
        return bool(out.strip())
    except Exception:
        return True


def run_single_task_cli(
    path: Path,
    budget: Budget,
    seed: int,
    partition: str = "evaluation",
    out_file: Path | None = None,
) -> dict[str, Any]:
    from euclid.runtime import EuclidRuntime

    hashes = _manifest_hashes()
    rel = path.relative_to(ROOT).as_posix() if ROOT in path.parents else None
    expected_hash = hashes.get(rel) if rel else None
    public = load_public_task(path, expected_hash)
    with tempfile.TemporaryDirectory(prefix="euclid-arc-single-") as state_dir:
        runtime = EuclidRuntime(creator_id="arc-worker", state_dir=Path(state_dir))
        try:
            runtime.compose_adaptive_intelligence()
            rec = run_task(runtime, public, budget, seed=seed, partition=partition)
        finally:
            runtime.close()
    if out_file:
        out_file.write_text(json.dumps(rec), encoding="utf-8")
    return rec


def run_split(
    split: str,
    *,
    limit: int | None,
    out_dir: Path,
    budget: Budget,
    seed: int,
    task_ids: list[str] | None = None,
    worker_isolation: str = "fresh_runtime",
) -> Path:
    from euclid.runtime import EuclidRuntime

    hashes = _manifest_hashes()
    paths = sorted((ROOT / "data" / split).glob("*.json"))
    if task_ids:
        wanted = set(task_ids)
        paths = [p for p in paths if p.stem in wanted]
    if limit is not None:
        paths = paths[:limit]
    out_dir.mkdir(parents=True, exist_ok=True)
    partition = "train" if split == "training" else "evaluation"

    submission: dict[str, list[dict[str, Any]]] = {}
    counts = {"completed": 0, "error": 0, "timeout": 0, "refusal": 0, "train_solved": 0}
    started = datetime.now(timezone.utc)

    def _execute_task_isolated_subprocess(index: int, path: Path, public: dict[str, Any]) -> dict[str, Any]:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            tmp_out = Path(tf.name)
        cmd = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--single-task",
            str(path),
            "--single-task-out",
            str(tmp_out),
            "--seed",
            str(seed + index),
            "--split",
            split,
            "--probe-budget",
            str(budget.probe_budget),
            "--submission-budget",
            str(budget.submission_budget),
            "--wall-clock-seconds",
            str(budget.wall_clock_seconds),
        ]
        t0 = time.perf_counter()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=budget.wall_clock_seconds + 5.0,
                check=False,
            )
            elapsed = time.perf_counter() - t0
            if tmp_out.exists() and tmp_out.stat().st_size > 0:
                rec = json.loads(tmp_out.read_text(encoding="utf-8"))
            elif proc.returncode == 0 and proc.stdout.strip():
                rec = json.loads(proc.stdout.strip().splitlines()[-1])
            else:
                rec = {
                    "task_id": public["task_id"],
                    "partition": partition,
                    "status": "error",
                    "error": proc.stderr.strip() or f"Subprocess exited with code {proc.returncode}",
                    "train_solved": False,
                    "probes": 0,
                    "submissions": 0,
                    "programmes": [],
                    "attempt_sources": ["no_candidate", "no_candidate"],
                    "episode": {},
                    "elapsed_seconds": round(elapsed, 3),
                    "attempts": [
                        {"attempt_1": NO_CANDIDATE, "attempt_2": NO_CANDIDATE}
                        for _ in public["test"]
                    ],
                }
        except subprocess.TimeoutExpired:
            elapsed = time.perf_counter() - t0
            rec = {
                "task_id": public["task_id"],
                "partition": partition,
                "status": "timeout",
                "error": f"WallClockTimeout: Task exceeded hard deadline of {budget.wall_clock_seconds}s",
                "train_solved": False,
                "probes": 0,
                "submissions": 0,
                "programmes": [],
                "attempt_sources": ["no_candidate", "no_candidate"],
                "episode": {},
                "elapsed_seconds": round(min(elapsed, budget.wall_clock_seconds), 3),
                "attempts": [
                    {"attempt_1": NO_CANDIDATE, "attempt_2": NO_CANDIDATE}
                    for _ in public["test"]
                ],
            }
        finally:
            if tmp_out.exists():
                try:
                    tmp_out.unlink()
                except OSError:
                    pass
        return rec

    with (out_dir / "records.jsonl").open("w", encoding="utf-8") as records:
        if worker_isolation == "shared_runtime":
            with tempfile.TemporaryDirectory(prefix="euclid-arc-") as state_dir:
                runtime = EuclidRuntime(creator_id="arc-agi-1-runner", state_dir=Path(state_dir))
                try:
                    runtime.compose_adaptive_intelligence()
                    for index, path in enumerate(paths):
                        rel = path.relative_to(ROOT).as_posix()
                        public = load_public_task(path, hashes.get(rel))
                        rec = run_task(
                            runtime, public, budget, seed=seed + index, partition=partition
                        )
                        submission[rec["task_id"]] = rec.pop("attempts")
                        counts[rec["status"]] = counts.get(rec["status"], 0) + 1
                        counts["train_solved"] += int(bool(rec.get("train_solved")))
                        records.write(json.dumps(rec) + "\n")
                        records.flush()
                        print(
                            f"[{index + 1}/{len(paths)}] {rec['task_id']} {rec['status']} "
                            f"train_solved={rec.get('train_solved')} "
                            f"{rec.get('elapsed_seconds')}s",
                            flush=True,
                        )
                finally:
                    runtime.close()
        elif worker_isolation == "subprocess":
            for index, path in enumerate(paths):
                rel = path.relative_to(ROOT).as_posix()
                public = load_public_task(path, hashes.get(rel))
                rec = _execute_task_isolated_subprocess(index, path, public)
                submission[rec["task_id"]] = rec.pop("attempts")
                counts[rec["status"]] = counts.get(rec["status"], 0) + 1
                counts["train_solved"] += int(bool(rec.get("train_solved")))
                records.write(json.dumps(rec) + "\n")
                records.flush()
                print(
                    f"[{index + 1}/{len(paths)}] {rec['task_id']} {rec['status']} "
                    f"train_solved={rec.get('train_solved')} "
                    f"{rec.get('elapsed_seconds')}s",
                    flush=True,
                )
        else:  # fresh_runtime (default)
            for index, path in enumerate(paths):
                rel = path.relative_to(ROOT).as_posix()
                public = load_public_task(path, hashes.get(rel))
                with tempfile.TemporaryDirectory(prefix=f"euclid-arc-{public['task_id']}-") as task_state:
                    runtime = EuclidRuntime(creator_id=f"arc-task-{index}", state_dir=Path(task_state))
                    try:
                        runtime.compose_adaptive_intelligence()
                        rec = run_task(
                            runtime, public, budget, seed=seed + index, partition=partition
                        )
                    finally:
                        runtime.close()
                        del runtime
                        gc.collect()

                submission[rec["task_id"]] = rec.pop("attempts")
                counts[rec["status"]] = counts.get(rec["status"], 0) + 1
                counts["train_solved"] += int(bool(rec.get("train_solved")))
                records.write(json.dumps(rec) + "\n")
                records.flush()
                print(
                    f"[{index + 1}/{len(paths)}] {rec['task_id']} {rec['status']} "
                    f"train_solved={rec.get('train_solved')} "
                    f"{rec.get('elapsed_seconds')}s",
                    flush=True,
                )

    (out_dir / "submission.json").write_text(json.dumps(submission), encoding="utf-8")
    manifest = {
        "protocol": PROTOCOL_VERSION,
        "split": split,
        "tasks_attempted": len(paths),
        "task_order": "sorted task id",
        "knowledge": f"worker_isolation={worker_isolation}; demonstration-world outcomes; no custody attached",
        "worker_isolation": worker_isolation,
        "budget": asdict(budget),
        "seed": seed,
        "git_head": _git_head(),
        "git_dirty_euclid": _git_dirty(),
        "python": sys.version.split()[0],
        "started_utc": started.isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "status_counts": counts,
        "test_outputs_read_by_runner": False,
        "note": "train_solved counts demonstration reproduction only; it is NOT a test score. Score with score_arc.py.",
    }
    (out_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return out_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--split", choices=("training", "evaluation"), default="training")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--task", action="append", default=None, help="restrict to task id(s)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--probe-budget", type=int, default=Budget.probe_budget)
    parser.add_argument("--submission-budget", type=int, default=Budget.submission_budget)
    parser.add_argument("--wall-clock-seconds", type=float, default=Budget.wall_clock_seconds)
    parser.add_argument(
        "--worker-isolation",
        choices=("fresh_runtime", "subprocess", "shared_runtime"),
        default="fresh_runtime",
        help="task worker isolation mode (default: fresh_runtime)",
    )
    parser.add_argument("--single-task", type=Path, default=None, help="run a single task in worker mode")
    parser.add_argument("--single-task-out", type=Path, default=None, help="output file for single task record")
    args = parser.parse_args(argv)

    budget = Budget(
        probe_budget=args.probe_budget,
        submission_budget=args.submission_budget,
        wall_clock_seconds=args.wall_clock_seconds,
    )

    if args.single_task:
        rec = run_single_task_cli(
            args.single_task,
            budget,
            seed=args.seed,
            partition="train" if args.split == "training" else "evaluation",
            out_file=args.single_task_out,
        )
        print(json.dumps(rec))
        return 0

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or ROOT / "runs" / f"{args.split}-{stamp}"
    run_split(
        args.split,
        limit=args.limit,
        out_dir=out,
        budget=budget,
        seed=args.seed,
        task_ids=args.task,
        worker_isolation=args.worker_isolation,
    )
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Run the actual TURING package and persist immutable, labelled evidence.

This is an exact package-validation experiment, not a performance/advantage study.
A source ZIP may be used with --allow-unversioned, but cannot become clean
commit-bound publication evidence merely by setting a flag or supplying a SHA.
"""

from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import platform
import subprocess
from time import perf_counter_ns
from uuid import uuid4

SCHEMA = "turing.experiment_manifest.v1"
CASES = ("bell_z0", "radical_z0", "finite_variational_z0")
PROJECT = Path(__file__).resolve().parents[1]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def source_identity(root: Path):
    def git(*args):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None

    top = git("rev-parse", "--show-toplevel")
    if top is None or Path(top).resolve() != root.resolve():
        return {"commit": None, "state": "unversioned", "dirty": None}
    commit = git("rev-parse", "HEAD")
    status = git("status", "--porcelain", "--untracked-files=normal")
    if commit is None or status is None:
        raise RuntimeError("Cannot inspect source identity; refusing to guess")
    return {"commit": commit, "state": "dirty" if status else "clean", "dirty": bool(status)}


def load_config(path):
    config = json.loads(Path(path).read_text())
    if set(config) != {"schema", "experiment_id", "repetitions", "execution", "cases"}:
        raise ValueError("Unexpected/missing configuration keys")
    if config["schema"] != "turing.experiment_config.v1":
        raise ValueError("Unsupported configuration schema")
    identifier = config["experiment_id"]
    if (
        not isinstance(identifier, str)
        or not identifier
        or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for c in identifier)
    ):
        raise ValueError("experiment_id must be a safe nonempty identifier")
    if type(config["repetitions"]) is not int or not 1 <= config["repetitions"] <= 100:
        raise ValueError("repetitions must be in 1..100")
    if (
        not config["cases"]
        or len(set(config["cases"])) != len(config["cases"])
        or any(c not in CASES for c in config["cases"])
    ):
        raise ValueError("Unknown, duplicate or empty case list")
    if set(config["execution"]) != {"backend", "execution_mode", "seed", "max_amplitudes"}:
        raise ValueError("Unexpected/missing execution keys")
    return config


def evaluate(turing, case):
    from turing_universal_quantum_computer import (
        FiniteAnsatz,
        ParameterBindings,
        ParameterSpec,
        PauliZ,
    )
    from turing_universal_quantum_computer.backends.base import Program

    if case == "bell_z0":
        estimate = turing.estimate(Program(2).then("h", 0).then("cx", 0, 1), observable=PauliZ(0))
        expected = ("0", "0")
        history = [estimate]
    elif case == "radical_z0":
        estimate = turing.estimate(
            Program(1).then("h", 0).then("t", 0).then("h", 0), observable=PauliZ(0)
        )
        expected = ("0", "1/2")
        history = [estimate]
    elif case == "finite_variational_z0":
        family = FiniteAnsatz.from_builder(
            (ParameterSpec("choice", (0, 1, 2)),),
            lambda p: (Program(1), Program(1).then("h", 0), Program(1).then("x", 0))[
                int(p.values[0])
            ],
        )
        optimized = turing.run_vqe(
            family, ParameterBindings(("choice",), (0,)), observable=PauliZ(0), max_iterations=3
        )
        if (
            not optimized.converged
            or optimized.termination_reason != "finite_domain_exhausted"
            or optimized.parameters.values != (2.0,)
        ):
            raise AssertionError(
                "finite optimization did not exhaust and minimize the declared domain"
            )
        history = [e.estimate for e in optimized.history]
        estimate = next(
            e.estimate for e in optimized.history if e.parameters == optimized.parameters
        )
        expected = ("-1", "0")
    else:
        raise ValueError("Unknown case")
    if estimate.exact_coefficients != expected:
        raise AssertionError(f"{case}: exact analytic reference mismatch")
    return {
        "case": case,
        "value": estimate.value,
        "exact_coefficients": list(estimate.exact_coefficients),
        "reference_coefficients": list(expected),
        "reference": "analytic_single_qubit_z_identity_or_explicit_finite_domain",
        "observable": {"kind": "PauliZ", "qubit": 0},
        "standard_error": estimate.standard_error,
        "uncertainty_method": estimate.uncertainty_method,
        "shots": estimate.shots,
        "evaluations": len(history),
        "verified": True,
        "jobs": [
            {
                "job_id": e.job_result.job_id,
                "request_hash": e.job_result.request_hash,
                "evidence": e.job_result.report(),
            }
            for e in history
        ],
    }


def run(config_path, output, *, allow_unversioned=False, allow_dirty=False):
    # Require the installed/current real package, never silently re-home imports here.
    from turing_universal_quantum_computer import TuringPipeline, PipelineConfig

    config = load_config(config_path)
    pipeline_config = PipelineConfig(**config["execution"])
    identity = source_identity(PROJECT.parent)
    if identity["state"] == "unversioned" and not allow_unversioned:
        raise RuntimeError(
            "A source ZIP has no commit identity; use --allow-unversioned for labelled local validation only"
        )
    if identity["state"] == "dirty" and not allow_dirty:
        raise RuntimeError(
            "Commit-bound runs require a clean checkout; --allow-dirty labels development evidence"
        )
    run_id = config["experiment_id"] + "-" + uuid4().hex
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / (run_id + ".json")
    dependencies = {}
    for distribution in ("hyba-turing-vqc", "hyba-kellogg-tensor", "numpy", "sympy"):
        try:
            dependencies[distribution] = version(distribution)
        except PackageNotFoundError:
            dependencies[distribution] = "NOT_INSTALLED_AS_DISTRIBUTION"
    manifest = {
        "schema": SCHEMA,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "running",
        "source": identity,
        "qualification": (
            "clean_commit_bound" if identity["state"] == "clean" else "development_only"
        ),
        "configuration": config,
        "configuration_hash": digest(config),
        "lock_sha256": hashlib.sha256((PROJECT / "uv.lock").read_bytes()).hexdigest(),
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": dependencies,
        },
        "measurements": [],
    }
    failure = None
    try:
        with TuringPipeline(pipeline_config) as turing:
            for repetition in range(config["repetitions"]):
                for case in config["cases"]:
                    before = perf_counter_ns()
                    measurement = evaluate(turing, case)
                    measurement["wall_time_ns"] = perf_counter_ns() - before
                    measurement["repetition"] = repetition
                    manifest["measurements"].append(measurement)
        manifest["status"] = "completed"
    except Exception as exc:
        failure = exc
        manifest["status"] = "failed"
        manifest["failure"] = {"type": type(exc).__name__, "message": str(exc)}
    manifest["manifest_digest"] = digest(manifest)
    with manifest_path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    if failure is not None:
        raise RuntimeError(
            f"Experiment failed; diagnostic manifest: {manifest_path.name}"
        ) from failure
    return manifest_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=PROJECT / "experiments/configs/exact_package_validation.json"
    )
    parser.add_argument("--output", type=Path, default=PROJECT / "results/local")
    parser.add_argument("--allow-unversioned", action="store_true")
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    print(
        run(
            args.config,
            args.output,
            allow_unversioned=args.allow_unversioned,
            allow_dirty=args.allow_dirty,
        )
    )


if __name__ == "__main__":
    main()

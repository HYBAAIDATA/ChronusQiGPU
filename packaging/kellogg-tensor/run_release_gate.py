"""Execute the source-level KELLOGG 1.0.0 release gate.

This is the complement to build_and_verify.py: it runs the current checkout's
KELLOGG product/boundary tests and the complete correctness/cost/meta benchmark
suite, then retains machine-readable evidence. Cross-version digest equality is
resolved by the workflow matrix after every supported interpreter has produced
its installed-wheel fixture.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
EVIDENCE = HERE / "release-evidence"
BENCH_RESULTS = REPO / "benchmarks" / "tensor" / "results"

TEST_FILES = (
    "tests/test_canonical_tensor_ownership.py",
    "tests/test_exact_tensor_parity.py",
    "tests/test_geodesic_tensor_engine.py",
    "tests/test_geodesic_tensor_extensions.py",
    "tests/test_kellogg_exact_linear_algorithm_audit.py",
    "tests/test_kellogg_exact_linear_field_audit.py",
    "tests/test_kellogg_product.py",
    "tests/test_kellogg_plan_admission.py",
    "tests/test_kellogg_production_evidence_boundary.py",
    "tests/test_kellogg_tensor.py",
    "tests/test_kellogg_tensor_network_convergence.py",
    "tests/test_toe_tensor_ml.py",
)


def git_sha() -> str:
    return subprocess.check_output(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True
    ).strip()


def _junit_counts(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    if root.tag == "testsuite":
        suites = [root]
    else:
        suites = list(root.findall("testsuite"))
    return {
        "collected": sum(int(s.attrib.get("tests", 0)) for s in suites),
        "failed": sum(int(s.attrib.get("failures", 0)) for s in suites),
        "errors": sum(int(s.attrib.get("errors", 0)) for s in suites),
        "skipped": sum(int(s.attrib.get("skipped", 0)) for s in suites),
        "duration_seconds": sum(float(s.attrib.get("time", 0.0)) for s in suites),
    }


def run_tests() -> dict[str, Any]:
    missing = [name for name in TEST_FILES if not (REPO / name).exists()]
    if missing:
        raise RuntimeError(f"release test files missing: {missing}")
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    junit = EVIDENCE / "tests-junit.xml"
    junit.unlink(missing_ok=True)
    test_files = sorted(set(TEST_FILES) | {
        str(path.relative_to(REPO)) for pattern in ("tests/test_kellogg*.py", "kellogg/**/test*.py")
        for path in REPO.glob(pattern)
    })
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        *test_files,
        f"--junitxml={junit}",
    ]
    started = time.perf_counter()
    proc = subprocess.run(command, cwd=REPO)
    elapsed = time.perf_counter() - started
    counts = _junit_counts(junit)
    counts["wall_seconds"] = elapsed
    counts["passed"] = (
        counts["collected"] - counts["failed"] - counts["errors"] - counts["skipped"]
    )
    evidence = {
        "command": command,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_sha": git_sha(),
        **counts,
        "returncode": proc.returncode,
    }
    (EVIDENCE / "tests.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8"
    )
    if (proc.returncode != 0 or counts["failed"] or counts["errors"]
            or counts["skipped"] or counts["collected"] <= 0):
        raise RuntimeError(f"KELLOGG release tests failed: {evidence}")
    return evidence


def run_benchmarks() -> dict[str, Any]:
    command = [sys.executable, "-m", "benchmarks.tensor.run_all"]
    latest = BENCH_RESULTS / "latest.json"
    latest.unlink(missing_ok=True)
    started = time.perf_counter()
    proc = subprocess.run(command, cwd=REPO)
    elapsed = time.perf_counter() - started
    if not latest.exists():
        raise RuntimeError("benchmark suite did not write benchmarks/tensor/results/latest.json")
    summary = json.loads(latest.read_text(encoding="utf-8"))

    from kellogg.benchmark import BENCHMARKS

    expected = set(BENCHMARKS)
    artifacts = summary.get("artifacts", [])
    observed = {row.get("benchmark_id") for row in artifacts}
    missing = sorted(expected - observed)
    extra = sorted(observed - expected)
    metadata_problems = []
    if len(artifacts) != len(observed):
        metadata_problems.append({"error": "duplicate benchmark IDs"})
    for row in artifacts:
        if row.get("commit") != git_sha():
            metadata_problems.append({"error": "stale benchmark commit", "benchmark_id": row.get("benchmark_id")})
        required = (
            "benchmark_id",
            "commit",
            "timestamp",
            "kellogg_version",
            "software",
            "configuration",
            "parameters",
            "result",
            "classification",
            "passed",
            "measurement",
            "digest",
        )
        absent = [key for key in required if key not in row]
        if absent:
            metadata_problems.append({"benchmark_id": row.get("benchmark_id"), "missing": absent})
    evidence = {
        "command": command,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_sha": git_sha(),
        "wall_seconds": elapsed,
        "returncode": proc.returncode,
        "expected_benchmarks": len(expected),
        "observed_benchmarks": len(observed),
        "passed": summary.get("passed", []),
        "failed": summary.get("failed", []),
        "incomplete": summary.get("incomplete", []),
        "missing": missing,
        "extra": extra,
        "metadata_problems": metadata_problems,
        "suite_digest": summary.get("digest"),
    }
    (EVIDENCE / "benchmarks.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8"
    )
    # cross_version_digest may be INCOMPLETE in this single-interpreter job;
    # the workflow's four-wheel matrix is the authoritative cross-version gate.
    unexpected_incomplete = [
        name for name in evidence["incomplete"] if name != "cross_version_digest"
    ]
    if (
        proc.returncode != 0
        or evidence["failed"]
        or missing
        or extra
        or metadata_problems
        or unexpected_incomplete
    ):
        raise RuntimeError(f"KELLOGG benchmark release gate failed: {evidence}")
    return evidence


def main() -> int:
    tests = run_tests()
    benchmarks = run_benchmarks()
    summary = {
        "product": "hyba-kellogg-tensor",
        "version": "1.0.0",
        "repository": "QuantumPhiRedux/PhiMiner",
        "git_sha": git_sha(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "tests": tests,
        "benchmarks": benchmarks,
        "tests_passed": True,
        "benchmarks_completed": True,
        "cross_version_verified": False,
        "publishable": False,
        "published": False,
        "scope": "source tests + complete benchmark suite; cross-version/artifact gates separate",
    }
    (EVIDENCE / "source-gate.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Critical mutation sentinels for production closure.

Each sentinel first proves its focused test is green against an untouched
detached worktree, plants one deliberate production defect, then requires the
same test to fail. A surviving mutant or a broken baseline fails the gate.

No mutation is made in the caller's checkout and no mutation is committed.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class MutationSpec:
    name: str
    path: str
    before: str
    after: str
    test: str
    expected_occurrences: int = 1


SPECS: dict[str, MutationSpec] = {
    "toe-engine-fail-closed": MutationSpec(
        name="toe-engine-fail-closed",
        path="toe/runtime.py",
        before=(
            "        # 3. Check engine availability\n"
            "        try:\n"
            "            if not self.bridge.available():\n"
        ),
        after=(
            "        # 3. Check engine availability\n"
            "        try:\n"
            "            if False:  # MUTATION: unavailable engine allowed\n"
        ),
        test=(
            "tests/test_toe_runtime.py::TestTOEIntelligenceRuntime::"
            "test_fail_closed_on_engine_unavailable"
        ),
    ),
    "toe-feedback-connected": MutationSpec(
        name="toe-feedback-connected",
        path="toe/runtime.py",
        before="        decision_id = self._record_decision(tenant, operation, result, confidence)\n",
        after="        decision_id = None  # MUTATION: feedback/evidence recording disconnected\n",
        test=(
            "tests/test_toe_runtime.py::TestTOEIntelligenceRuntime::"
            "test_predict_records_decision_in_feedback"
        ),
    ),
    "toe-evidence-connected": MutationSpec(
        name="toe-evidence-connected",
        path="toe/runtime.py",
        before=(
            "        if self.evidence_chain is not None:\n"
            "            try:\n"
            "                self.evidence_chain.append(\n"
            "                    \"toe-prediction\",\n"
        ),
        after=(
            "        if False and self.evidence_chain is not None:  # MUTATION: evidence disabled\n"
            "            try:\n"
            "                self.evidence_chain.append(\n"
            "                    \"toe-prediction\",\n"
        ),
        test=(
            "tests/test_toe_runtime.py::TestTOEIntelligenceRuntime::"
            "test_predict_appends_evidence"
        ),
    ),
    "hendrix-order-preserved": MutationSpec(
        name="hendrix-order-preserved",
        path="chronus/mla1517/mining/hendrix_order.py",
        before=(
            "    return [(base + schedule.nonce_at(p)) & 0xFFFFFFFF "
            "for p in range(position, position + count)]\n"
        ),
        after=(
            "    return [(base + p) & 0xFFFFFFFF "
            "for p in range(position, position + count)]  # MUTATION: sequential\n"
        ),
        test=(
            "chronus/mla1517_platform/python/test_hendrix_nonce_order.py::"
            "test_order_is_a_stride_permutation_not_the_sequential_sweep"
        ),
    ),
    "turing-measurement-collapse": MutationSpec(
        name="turing-measurement-collapse",
        path=(
            "turing_universal_quantum_computer/"
            "turing_universal_quantum_computer/stabilizer.py"
        ),
        before="            self._r[pivot] = int(outcome)\n",
        after="            self._r[pivot] = 0  # MUTATION: collapse ignores outcome\n",
        test=(
            "turing_universal_quantum_computer/tests/"
            "test_stabilizer_measurement.py::"
            "test_both_random_measurement_branches_match_dense_statevector"
        ),
    ),
    "sha256d-independent-recheck": MutationSpec(
        name="sha256d-independent-recheck",
        path="mining/hash_pipeline.py",
        before=(
            "        # Independent consensus recheck at the pipeline boundary.  A backend\n"
            "        # candidate is never returned merely because it reported a hit.\n"
            "        if winner is not None:\n"
            "            reference = double_sha256(header80[:76] + "
            "struct.pack(\"<I\", int(winner) & 0xFFFFFFFF))\n"
            "            if win_hash != reference or reference[::-1] > target_be:\n"
        ),
        after=(
            "        # Independent consensus recheck at the pipeline boundary.  A backend\n"
            "        # candidate is never returned merely because it reported a hit.\n"
            "        if winner is not None:\n"
            "            reference = double_sha256(header80[:76] + "
            "struct.pack(\"<I\", int(winner) & 0xFFFFFFFF))\n"
            "            if False:  # MUTATION: backend candidate trusted without recheck\n"
        ),
        test=(
            "tests/test_mining_consensus_recheck.py::"
            "test_backend_candidate_must_survive_independent_sha256d_recheck"
        ),
    ),
    "sha256d-m32-independent-recheck": MutationSpec(
        name="sha256d-m32-independent-recheck",
        path="mining/hash_pipeline.py",
        before=(
            "            header80, target_be, base_nonce, lane_order, count\n"
            "        )\n"
            "        if winner is not None:\n"
            "            reference = double_sha256(header80[:76] + "
            "struct.pack(\"<I\", int(winner) & 0xFFFFFFFF))\n"
            "            if win_hash != reference or reference[::-1] > target_be:\n"
            "                raise RuntimeError(\"backend candidate failed independent SHA-256d target recheck\")\n"
            "        el = time.perf_counter() - t0\n"
        ),
        after=(
            "            header80, target_be, base_nonce, lane_order, count\n"
            "        )\n"
            "        if winner is not None:\n"
            "            reference = double_sha256(header80[:76] + "
            "struct.pack(\"<I\", int(winner) & 0xFFFFFFFF))\n"
            "            if False:  # MUTATION: M32 backend candidate trusted without recheck\n"
            "                raise RuntimeError(\"backend candidate failed independent SHA-256d target recheck\")\n"
            "        el = time.perf_counter() - t0\n"
        ),
        test=(
            "tests/test_mining_consensus_recheck.py::"
            "test_m32_backend_candidate_must_survive_independent_sha256d_recheck"
        ),
    ),
}


@dataclass(frozen=True)
class MutationResult:
    name: str
    path: str
    test: str
    status: str
    baseline_returncode: int | None
    mutant_returncode: int | None
    reason: str
    baseline_tail: tuple[str, ...] = ()
    mutant_tail: tuple[str, ...] = ()


def _tail(text: str, count: int = 12) -> tuple[str, ...]:
    return tuple(line for line in text.splitlines() if line.strip())[-count:]


def _run_test(worktree: Path, spec: MutationSpec) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    prefixes = [
        str(worktree),
        str(worktree / "turing_universal_quantum_computer"),
        str(worktree / "chronus" / "mla1517_platform" / "python"),
    ]
    existing = env.get("PYTHONPATH")
    if existing:
        prefixes.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(prefixes)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "pytest", spec.test, "-q", "-p", "no:cacheprovider"],
        cwd=worktree,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=180,
    )


def _worktree(path: Path) -> None:
    proc = subprocess.run(
        ["git", "worktree", "add", "--detach", "--quiet", str(path), "HEAD"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode:
        raise RuntimeError(f"git worktree add failed: {proc.stderr.strip()}")


def _remove_worktree(path: Path) -> None:
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(path)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def apply_mutation(path: Path, spec: MutationSpec) -> None:
    source = path.read_text(encoding="utf-8")
    occurrences = source.count(spec.before)
    if occurrences != spec.expected_occurrences:
        raise RuntimeError(
            f"{spec.name}: expected {spec.expected_occurrences} source anchor(s), "
            f"found {occurrences} in {spec.path}"
        )
    path.write_text(source.replace(spec.before, spec.after, 1), encoding="utf-8")


def run_spec(spec: MutationSpec) -> MutationResult:
    with tempfile.TemporaryDirectory(prefix=f"mutation-{spec.name}-") as tmp:
        worktree = Path(tmp) / "repo"
        _worktree(worktree)
        try:
            baseline = _run_test(worktree, spec)
            if baseline.returncode != 0:
                return MutationResult(
                    spec.name,
                    spec.path,
                    spec.test,
                    "BASELINE_FAILED",
                    baseline.returncode,
                    None,
                    "focused test is not green before mutation",
                    _tail(baseline.stdout),
                    (),
                )

            try:
                apply_mutation(worktree / spec.path, spec)
            except Exception as exc:
                return MutationResult(
                    spec.name,
                    spec.path,
                    spec.test,
                    "MUTATION_ERROR",
                    baseline.returncode,
                    None,
                    str(exc),
                    _tail(baseline.stdout),
                    (),
                )

            mutant = _run_test(worktree, spec)
            if mutant.returncode == 0:
                return MutationResult(
                    spec.name,
                    spec.path,
                    spec.test,
                    "SURVIVED",
                    baseline.returncode,
                    mutant.returncode,
                    "planted critical defect was not detected by its focused test",
                    _tail(baseline.stdout),
                    _tail(mutant.stdout),
                )
            return MutationResult(
                spec.name,
                spec.path,
                spec.test,
                "KILLED",
                baseline.returncode,
                mutant.returncode,
                "green baseline turned red after the planted defect",
                _tail(baseline.stdout),
                _tail(mutant.stdout),
            )
        finally:
            _remove_worktree(worktree)


def _write_report(path: Path, results: Sequence[MutationResult]) -> None:
    payload = {
        "schema_version": 1,
        "source_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "passed": all(r.status == "KILLED" for r in results),
        "results": [asdict(r) for r in results],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mutation", choices=sorted(SPECS))
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--json", dest="json_path")
    args = parser.parse_args(argv)

    if args.list:
        print("\n".join(sorted(SPECS)))
        return 0
    if args.all == bool(args.mutation):
        parser.error("choose exactly one of --all or --mutation")

    selected = list(SPECS.values()) if args.all else [SPECS[args.mutation]]
    results = [run_spec(spec) for spec in selected]
    if args.json_path:
        _write_report(ROOT / args.json_path, results)
    print(
        json.dumps(
            {
                "passed": all(r.status == "KILLED" for r in results),
                "results": [asdict(r) for r in results],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if all(r.status == "KILLED" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

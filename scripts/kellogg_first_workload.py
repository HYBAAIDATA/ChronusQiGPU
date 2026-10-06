"""Kellogg first workload — executable contract run.

Implements ``kellogg.first-workload/1`` (docs/kellogg/FIRST_WORKLOAD.md):

  store (custody) → committed kron → independent re-verification →
  receipt → attestation → checkpoint → fresh restore → re-execution
  replay → verdict JSON.

The verdict binds the executing commit's ``git_head`` and every stage's
evidence digests. A failing stage records ``verdict: fail`` and exits
nonzero — it never fakes a pass.

Usage::

    python scripts/kellogg_first_workload.py [--workdir DIR]

Exit 0 iff every stage passes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from aethel.fold_store import PersistentFoldStore  # noqa: E402
from tensor.api import TensorRuntime  # noqa: E402

WORKLOAD_ID = "kellogg.first-workload/1"


def _git_head() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:
        return "UNKNOWN"


def run_workload(workdir: Path) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    stages = {}

    # -- Stage 1: custody of inputs --------------------------------------
    rt = TensorRuntime()
    rng = np.random.default_rng
    a = rng(11).normal(size=(4, 4))
    b = rng(13).normal(size=(4, 4))
    in_a = rt.store_tensor("a", a)
    in_b = rt.store_tensor("b", b)
    stages["custody_inputs"] = {
        "a": in_a["content_hash"],
        "b": in_b["content_hash"],
        "verdict": "pass",
    }

    # -- Stage 2: committed execution + independent verification ----------
    record = rt.execute("kron", ["a", "b"], request_id="fw1")
    verified = (
        record["verification"]["verdict"] == "pass"
        and record["receipt"]["correctness"] == "verified"
        and record["path"] == "committed"
    )
    expected = np.kron(a, b)
    element_exact = np.array_equal(rt.read_tensor(record["output"]), expected)
    stages["execute"] = {
        "path": record["path"],
        "verification": record["verification"],
        "element_exact_vs_numpy": element_exact,
        "verdict": "pass" if verified and element_exact else "fail",
    }

    # -- Stage 3: attestation --------------------------------------------
    from kellogg.attest import attest

    attestation = attest(
        {
            "workload": WORKLOAD_ID,
            "request_id": record["request_id"],
            "output_hash": record["output_hash"],
            "steps": ["store", "execute", "verify"],
        },
        notes=["integrity binding only — correctness is receipt-level"],
    )
    stages["attest"] = {
        "digest": attestation["digest"],
        "version_lock": attestation["version_lock"],
        "theorem_proven": attestation["boundary"]["theorem_proven"],
        "verdict": "pass",
    }

    # -- Stage 4: custody checkpoint → fresh restore ----------------------
    checkpoint_path = workdir / "first_workload_store.npz"
    rt.store.checkpoint(checkpoint_path)
    restored_store = PersistentFoldStore.restore(checkpoint_path)
    restored_rt = TensorRuntime(store=restored_store)
    integrity_ok = (
        restored_rt.store.content_hash("a") == in_a["content_hash"]
        and restored_rt.store.content_hash("b") == in_b["content_hash"]
    )
    stages["custody_restore"] = {
        "checkpoint": str(checkpoint_path),
        "restored_names": list(restored_rt.tensor_names()),
        "content_hashes_preserved": integrity_ok,
        "verdict": "pass" if integrity_ok else "fail",
    }

    # -- Stage 5: replay — full re-execution on restored custody ----------
    replayed = restored_rt.execute("kron", ["a", "b"], request_id="fw1-replay")
    replay_ok = (
        replayed["output_hash"] == record["output_hash"]
        and replayed["verification"]["verdict"] == "pass"
    )
    stages["replay"] = {
        "original_output_hash": record["output_hash"],
        "replayed_output_hash": replayed["output_hash"],
        "identical": replayed["output_hash"] == record["output_hash"],
        "verdict": "pass" if replay_ok else "fail",
    }

    overall = all(s["verdict"] == "pass" for s in stages.values())
    return {
        "schema": "kellogg.first-workload-verdict/1",
        "workload_id": WORKLOAD_ID,
        "owner_approval": "pending",
        "git_head": _git_head(),
        "stages": stages,
        "claim_boundary": (
            "executed on this host's float64 committed path; no hardware, "
            "no exact-plane, no formal-proof claim"
        ),
        "verdict": "pass" if overall else "fail",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--workdir",
        type=Path,
        default=None,
        help="directory for the custody checkpoint artifact (default: tempdir)",
    )
    args = parser.parse_args()
    if args.workdir is None:
        with tempfile.TemporaryDirectory() as tmp:
            verdict = run_workload(Path(tmp))
    else:
        verdict = run_workload(args.workdir)
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0 if verdict["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

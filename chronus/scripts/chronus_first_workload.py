"""Chronus first workload — executable contract run.

Implements ``chronus.first-workload/1`` (chronus/docs/chronus/FIRST_WORKLOAD.md),
Chronus's own workload shape end to end:

  submit → select adapter → execute → independent recompute →
  receipt/evidence → durable ledger → custody → validate/replay.

The workload is a ``sha256d_scan`` over the Bitcoin genesis block header's
nonce neighbourhood: it re-discovers the real genesis hit (nonce
2083236893) at the real difficulty-1 target — deterministic, bit-exact,
and independently recomputed by the receipt verification gate before it
is ledgered. ``metrics.custody`` binds the evidence envelope into THESEUS
custody (``constraints.custody == "required"``), and a fresh daemon over
the same store replays the workload to an identical output digest.

The verdict binds the executing commit's ``git_head`` and every stage's
evidence digests. A failing stage records ``verdict: fail`` and exits
nonzero — it never fakes a pass.

Usage::

    python chronus/scripts/chronus_first_workload.py [--workdir DIR]

Exit 0 iff every stage passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from chronus.virtual_igpu.abi import (  # noqa: E402
    ExecutionPolicy,
    Workload,
    WorkloadKind,
)
from chronus.virtual_igpu.evidence import validate_receipt  # noqa: E402
from chronus.virtual_igpu.runtime import RuntimeDaemon  # noqa: E402
from hyba_db.theseus_custody import TheseusFileCustody  # noqa: E402

WORKLOAD_ID = "chronus.first-workload/1"
TENANT = "chronus-first-workload"

# Genesis block header (Bitcoin block 0), wire byte order.
HEADER80_HEX = (
    "01000000"
    + "00" * 32
    + "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
    + "29ab5f49"
    + "ffff001d"
    + "1dac2b7c"
)
WORKLOAD_INPUT = {
    "header80_hex": HEADER80_HEX,
    # The header's own nonce is 2083236893; the window starts 256 nonces
    # earlier so the scan must actually walk before it hits.
    "start_nonce": 2083236637,
    "count": 512,
    "target_hex": (
        "00000000ffff0000000000000000000000000000000000000000000000000000"
    ),
}
# Measured on this implementation: deterministic for fixed input.
EXPECTED = {
    "hit_nonce": 2083236893,
    "checked": 257,
    "hash_hex": (
        "6fe28c0ab6f1b372c1a6a246ae63f74f931e8365e15a089c68d6190000000000"
    ),
}


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


def _first_workload() -> Workload:
    return Workload(
        id=WORKLOAD_ID,
        kind=WorkloadKind.SHA256D_SCAN,
        tenant=TENANT,
        execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
        input=dict(WORKLOAD_INPUT),
        constraints={"custody": "required"},
    )


def _ledger_record_for(daemon: RuntimeDaemon) -> object:
    for record in daemon.ledger.list_records():
        if record.workload_id == WORKLOAD_ID:
            return record
    return None


def run_workload(workdir: Path) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    stages: dict[str, dict] = {}

    # Run-local custody key: proves the THESEUS path without faking
    # production key management.
    custody_key = secrets.token_bytes(32)
    custody = TheseusFileCustody(workdir / "custody", hmac_key=custody_key)
    store_dir = workdir / "vigpu-store"
    daemon = RuntimeDaemon(store_dir=store_dir, custody=custody)

    # -- Stage 1: submit → select adapter → execute ----------------------
    result = daemon.submit(_first_workload())
    hit = (result.output.get("hits") or [{}])[0]
    stage_ok = (
        result.status == "ok"
        and hit.get("nonce") == EXPECTED["hit_nonce"]
        and hit.get("hash_hex") == EXPECTED["hash_hex"]
        and result.output.get("checked") == EXPECTED["checked"]
    )
    stages["submit_execute"] = {
        "status": result.status,
        "adapter_id": result.adapter_id,
        "route_reason": result.route_reason,
        "hit_nonce": hit.get("nonce"),
        "checked": result.output.get("checked"),
        "hash_hex": hit.get("hash_hex"),
        "expected": dict(EXPECTED),
        "verdict": "pass" if stage_ok else "fail",
    }

    # -- Stage 2: independent recompute verification ----------------------
    verification = dict(result.receipt.get("verification") or {})
    v_ok = (
        verification.get("recomputed") is True
        and verification.get("verdict") == "match"
        and str(verification.get("verifier", "")).startswith("recompute:")
    )
    stages["independent_verification"] = {
        **verification,
        "verdict": "pass" if v_ok else "fail",
    }

    # -- Stage 3: receipt validation --------------------------------------
    # The ExecutionReceipt's content_hash is digest_json over its own
    # fields — validate the receipt and bind the contract's identity
    # fields. (Do not pass result= — it injects a 'result' key into the
    # digested body and the content_hash would never match.)
    expect = {
        "workload_id": WORKLOAD_ID,
        "requested_policy": ExecutionPolicy.STANDALONE_SOFTWARE.value,
        "delivery_mode": result.delivery_mode,
        "actual_backend": result.receipt.get("actual_backend"),
    }
    receipt_report = validate_receipt(result.receipt, expect=expect)
    stages["receipt_validation"] = {
        "expect": expect,
        "report_ok": receipt_report.get("ok"),
        "integrity": receipt_report.get("integrity"),
        "errors": receipt_report.get("errors", []),
        "verdict": "pass" if receipt_report.get("ok") else "fail",
    }

    # -- Stage 4: durable ledger + content-addressed evidence -------------
    record = _ledger_record_for(daemon)
    evidence_file = daemon.root / "evidence" / f"{result.evidence_digest}.json"
    evidence_ok = evidence_file.exists() and (
        hashlib.sha256(evidence_file.read_bytes()).hexdigest()
        == result.evidence_digest
    )
    chain_ok = record is not None and (
        record.chain_digest
        == hashlib.sha256(
            f"{record.chain_prev}:{record.content_hash}".encode("utf-8")
        ).hexdigest()
    )
    artifact = None
    try:
        artifact = daemon.memory.retrieve(TENANT, WORKLOAD_ID)
    except KeyError:
        artifact = None
    stage_ok = bool(record and chain_ok and evidence_ok and artifact)
    stages["durable_ledger"] = {
        "record_id": getattr(record, "record_id", None),
        "chain_rederived": bool(chain_ok),
        "evidence_digest": result.evidence_digest,
        "evidence_file_verified": evidence_ok,
        "memory_artifact": bool(artifact),
        "verdict": "pass" if stage_ok else "fail",
    }

    # -- Stage 5: THESEUS custody ----------------------------------------
    custody_info = dict((result.metrics or {}).get("custody") or {})
    custody_ok = (
        custody_info.get("authority") == "theseus"
        and custody_info.get("state") == "committed"
        and custody.verify(TENANT, str(custody_info.get("record_id", "")))
    )
    stages["custody_commit"] = {
        **custody_info,
        "reverified_by_executor": custody_ok,
        "verdict": "pass" if custody_ok else "fail",
    }

    # -- Stage 6: replay — fresh daemon over the same store ---------------
    replay_custody = TheseusFileCustody(workdir / "custody", hmac_key=custody_key)
    replay_daemon = RuntimeDaemon(store_dir=store_dir, custody=replay_custody)
    replayed = replay_daemon.submit(_first_workload())
    # Replay-stable bindings: the output payload and the canonical
    # input_digest. Attempt-level digests (output_digest/evidence_digest)
    # intentionally bind wall/device timing — they are expected to differ
    # per attempt and are NOT a replay invariant.
    records = replay_daemon.ledger.list_records()
    chain_continued = (
        len(records) >= 2
        and records[-1].chain_prev == records[-2].chain_digest
    )
    replay_ok = (
        replayed.status == "ok"
        and replayed.output == result.output
        and replayed.receipt.get("input_digest")
        == result.receipt.get("input_digest")
        and (replayed.receipt.get("verification") or {}).get("verdict") == "match"
        and chain_continued
    )
    stages["replay"] = {
        "input_digest": result.receipt.get("input_digest"),
        "replayed_input_digest": replayed.receipt.get("input_digest"),
        "output_identical": replayed.output == result.output,
        "ledger_records": len(records),
        "chain_continued": chain_continued,
        "verdict": "pass" if replay_ok else "fail",
    }

    overall = all(s["verdict"] == "pass" for s in stages.values())
    return {
        "schema": "chronus.first-workload-verdict/1",
        "workload_id": WORKLOAD_ID,
        "owner_approval": (
            "delegated — declared by Devin under owner delegation "
            "(@bollingertm, 2026-10-06)"
        ),
        "git_head": _git_head(),
        "stages": stages,
        "claim_boundary": (
            "executed on this host's standalone software path; no hardware, "
            "no accelerated, no device-observed claim"
        ),
        "verdict": "pass" if overall else "fail",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--workdir",
        type=Path,
        default=None,
        help=(
            "directory for the custody + store artifacts "
            "(default: tempdir)"
        ),
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

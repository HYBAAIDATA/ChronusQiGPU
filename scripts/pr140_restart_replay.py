"""Execute and independently replay local Genesis proof through canonical PYTHIA.

This check uses the installed ONE iGPU and local PRIME-DB. It produces no
external pool, device, deployed OVID/THESEUS, performance or release evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GENESIS = bytes.fromhex(
    "01000000"
    + "00" * 32
    + "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
    + "29ab5f49"
    + "ffff001d"
    + "1dac2b7c"
)
TARGET = (0xFFFF << (8 * (0x1D - 3))).to_bytes(32, "big")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("execute", "replay"))
    parser.add_argument("--variant", required=True, choices=("native", "portable"))
    parser.add_argument("--state-dir", required=True, type=Path)
    args = parser.parse_args(argv)

    import chronos_one_igpu
    from chronos_one_igpu import OneIGPU
    from chronos_one_igpu.igpu.execution_identity import verify_receipt

    package = Path(chronos_one_igpu.__file__).resolve()
    if "site-packages" not in package.parts:
        raise RuntimeError("installed artifact required; source-tree shadowing refused")
    native = importlib.util.find_spec("chronos_one_igpu.igpu._sha256d_native")
    if (native is not None) != (args.variant == "native"):
        raise RuntimeError("installed native/portable variant does not match the request")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", "chronus", "packages", "scripts"],
        cwd=ROOT,
        check=True,
    )
    args.state_dir.mkdir(parents=True, exist_ok=True)
    manifest = args.state_dir / "voyage.json"
    db = args.state_dir / "voyage.sqlite3"
    if args.phase == "execute":
        if manifest.exists() or db.exists():
            raise RuntimeError("fresh state required; old evidence cannot be rebound")
        from chronus.mla1517.mining.exact_search import exact_face_order, precompute_exact_search
        from chronus.mla1517.mining.resident_search import compile_hendrix_plan
        from chronus.mla1517.mining.search_plan import SearchPlan

        state = precompute_exact_search()
        order = exact_face_order(GENESIS, state)
        plan = SearchPlan(
            job_fingerprint=hashlib.sha256(GENESIS).hexdigest(),
            pool_session_id="local-genesis-no-pool",
            generation=1,
            base_step=2083236893,
            window=1,
            extranonce2="00000000",
            lane_order=order,
            preferred_face=order[0],
            dispatch_breadth=32,
            executor_route="chronus_batch",
            policy_id="hendrix",
            evidence_refs={
                "search_precompute_digest": state.digest,
                "search_architecture": state.architecture_id,
            },
            created_at=time.monotonic(),
            plan_id="local-genesis-canonical-qualification",
        )
        artifact = compile_hendrix_plan(plan, GENESIS, TARGET, state)
        artifact.require_context(plan, GENESIS, TARGET)
        with OneIGPU(db_path=db) as gpu:
            receipt = gpu.execute_hendrix(artifact.as_dict(), GENESIS, TARGET, position=0, count=1)
            if not verify_receipt(receipt, artifact.as_dict(), igpu=gpu):
                raise RuntimeError("independent execution verification failed")
            if (
                receipt["nonce"] != 2083236893
                or receipt["sha256d_evaluations"] != 1
                or receipt["fallback_used"]
                or receipt["physical_device_executed"]
            ):
                raise RuntimeError("Genesis execution identity mismatch")
        document = {
            "schema": "pr140.canonical_local_voyage/1",
            "source_commit": commit,
            "variant": args.variant,
            "package_file": str(package),
            "package_version": importlib.metadata.version("chronos-one-igpu"),
            "native_module": native.origin if native is not None else None,
            "database_sha256": sha256(db),
            "plan": artifact.as_dict(),
            "receipt": receipt,
        }
        manifest.write_text(json.dumps(document, indent=2, allow_nan=False) + "\n")
        result = {
            "phase": "execute",
            "source_commit": commit,
            "variant": args.variant,
            "genesis_sha256d": "INDEPENDENTLY_VERIFIED",
            "sha256d_evaluations": 1,
            "custody": "LOCAL_PRIME_DB",
            "pool_submitted": False,
        }
    else:
        document = json.loads(manifest.read_text())
        if (
            document["source_commit"] != commit
            or document["variant"] != args.variant
            or document["database_sha256"] != sha256(db)
        ):
            raise RuntimeError("replay source, variant or database binding mismatch")
        receipt = document["receipt"]
        persistence = receipt["persistence"]
        with OneIGPU(db_path=db) as gpu:
            plan = gpu.db.get(persistence["plan_object_id"]).payload
            restored = gpu.db.get(persistence["receipt_object_id"]).payload
            if (
                plan != document["plan"]
                or restored["receipt_digest"] != persistence["stored_receipt_digest"]
                or not verify_receipt(restored, plan, igpu=gpu)
            ):
                raise RuntimeError("fresh-process restore or SHA256d replay failed")
        result = {
            "phase": "replay",
            "source_commit": commit,
            "variant": args.variant,
            "independent_fresh_process_replay": True,
            "plan_digest": restored["resident_execution_digest"],
            "receipt_digest": restored["receipt_digest"],
            "sha256d_evaluations": restored["sha256d_evaluations"],
            "candidate_nonce": restored["nonce"],
            "custody": "LOCAL_PRIME_DB",
            "deployed_THESEUS_OVID": "UNAVAILABLE",
            "external_pool_acceptance": "UNAVAILABLE",
        }
        (args.state_dir / "replay.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

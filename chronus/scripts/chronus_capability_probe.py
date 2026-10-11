"""Measure what Chronus can do on THIS host, on real data, and emit one JSON artifact.

Run from the repo root:  python chronus/scripts/chronus_capability_probe.py [--out PATH] [--quick]

Honesty rules (same as chronus/README.md):
  * Real data = Bitcoin block headers that reproduce their published block hashes
    (checked at runtime) and this repository's own files. Anything else is labelled synthetic.
  * Only the software (CPU) adapter exists on a host without OpenCL/CUDA/Metal; the artifact
    records that and never turns a software result into a hardware claim.
  * Rates are wall-clock over the full submit path (admission, execution, independent control-plane
    recompute, receipt, evidence ledger) unless a row says "raw".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from chronus.mla1517.mining.execution_router import NONCE_ORDER_HENDRIX  # noqa: E402
from chronus.mla1517.mining.geodesic_support import ProductionExecutionRouter  # noqa: E402
from chronus.mla1517.mining.pythia_search import (  # noqa: E402
    SEARCH_ARCHITECTURE_ID,
    precompute_pythia_search,
)
from chronus.mla1517.mining.search_plan import NonceLease, SearchPlan  # noqa: E402
from chronus.virtual_igpu.abi import (  # noqa: E402
    ExecutionPolicy,
    ProductMode,
    Workload,
    WorkloadKind,
)
from chronus.virtual_igpu.adapters import CPUEmulatorAdapter  # noqa: E402
from chronus.virtual_igpu.client import ChronusClient  # noqa: E402
from chronus.virtual_igpu.evidence import validate_receipt  # noqa: E402
from chronus.virtual_igpu.mining_hasher import ChronusVirtualIGPUHasher  # noqa: E402
from chronus.virtual_igpu.runtime import RuntimeDaemon  # noqa: E402

# Real Bitcoin headers; each is accepted ONLY if SHA256d reproduces the published block hash.
REAL_BLOCKS = {
    "genesis_h0": (
        "0100000000000000000000000000000000000000000000000000000000000000000000003ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a29ab5f49ffff001d1dac2b7c",
        "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f",
    ),
    "block_h1": (
        "010000006fe28c0ab6f1b372c1a6a246ae63f74f931e8365e15a089c68d6190000000000982051fd1e4ba744bbbe680e1fee14677ba1a3c3540bf7b1cdb606e857233e0e61bc6649ffff001d01e36299",
        "00000000839a8e6886ab5951d76f411475428afc90947ee320161bbf18eb6048",
    ),
    "block_h125552": (
        "0100000081cd02ab7e569e8bcd9317e2fe99f2de44d49ab2b8851ba4a308000000000000e320b6c2fffc8d750423db8b1eb942ae710e951ed797f7affc8892b0f1fc122bc7f5d74df2b9441a42a14695",
        "00000000000000001e8d6829a8a21adc5d38d0a473b144b6765798e61f98bd1d",
    ),
}


def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def target_from_bits(bits: int) -> int:
    exponent, mantissa = bits >> 24, bits & 0x007FFFFF
    return mantissa * 256 ** (exponent - 3)


def verified_blocks() -> dict[str, dict]:
    out = {}
    for name, (header_hex, display_hash) in REAL_BLOCKS.items():
        header = bytes.fromhex(header_hex)
        digest = sha256d(header)
        if len(header) != 80 or digest[::-1].hex() != display_hash:
            raise SystemExit(f"{name}: header does not reproduce its published block hash")
        bits = int.from_bytes(header[72:76], "little")
        out[name] = {
            "header": header,
            "nonce": int.from_bytes(header[76:80], "little"),
            "bits": bits,
            "target": target_from_bits(bits),
            "block_hash": display_hash,
        }
    return out


def host_info() -> dict:
    cpu = "unknown"
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass
    mem_gb = None
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal"):
                mem_gb = round(int(line.split()[1]) / 1024 / 1024, 1)
                break
    except OSError:
        pass
    runtimes = {}
    for name in ("pyopencl", "cupy", "mlx", "torch"):
        try:
            __import__(name)
            runtimes[name] = "importable"
        except Exception:
            runtimes[name] = "absent"
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except Exception:
        sha = "unknown"
    return {
        "cpu": cpu,
        "logical_cpus": os.cpu_count(),
        "memory_gb": mem_gb,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_head": sha,
        "gpu_runtimes": runtimes,
        "physical_device_observed": (
            False if all(v == "absent" for v in runtimes.values()) else None
        ),
    }


class Probe:
    def __init__(self, quick: bool):
        self.quick = quick
        self.tmp = Path(tempfile.mkdtemp(prefix="chronus-probe-"))
        self.daemon = RuntimeDaemon(
            adapters=[CPUEmulatorAdapter()], store_dir=self.tmp / "rt", max_per_tenant=64
        )
        self.client = ChronusClient(daemon=self.daemon)
        self.seq = 0

    def submit(self, kind: WorkloadKind, payload: dict, **kw):
        self.seq += 1
        wl = Workload(
            id=f"probe-{self.seq}",
            kind=kind,
            tenant="probe",
            input=payload,
            execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
            **kw,
        )
        t0 = time.perf_counter()
        result = self.client.submit(wl)
        return result, time.perf_counter() - t0

    # --- SHA256d on real headers -------------------------------------------------------------
    def sha256d_correctness(self, blocks: dict) -> list[dict]:
        rows = []
        for name, block in blocks.items():
            nonce = block["nonce"]
            start = max(0, nonce - 1500)
            result, wall = self.submit(
                WorkloadKind.SHA256D_SCAN,
                {
                    "header80_hex": block["header"].hex(),
                    "target_hex": f"{block['target']:064x}",
                    "start_nonce": start,
                    "count": 3000,
                },
            )
            hits = result.output["hits"]
            rows.append(
                {
                    "block": name,
                    "published_hash": block["block_hash"],
                    "bits": hex(block["bits"]),
                    "real_nonce": nonce,
                    "found_nonce": hits[0]["nonce"] if hits else None,
                    "found_hash_display": (
                        bytes.fromhex(hits[0]["hash_hex"])[::-1].hex() if hits else None
                    ),
                    "nonces_checked": result.output["checked"],
                    "reproduces_real_block": bool(
                        hits
                        and hits[0]["nonce"] == nonce
                        and bytes.fromhex(hits[0]["hash_hex"])[::-1].hex() == block["block_hash"]
                    ),
                    "control_plane_verdict": result.receipt["verification"]["verdict"],
                    "wall_s": round(wall, 4),
                }
            )
        return rows

    def sha256d_throughput(self, block: dict) -> dict:
        sizes = [20_000, 100_000] if self.quick else [100_000, 500_000, 1_000_000]
        rows = []
        for count in sizes:
            result, wall = self.submit(
                WorkloadKind.SHA256D_SCAN,
                {
                    "header80_hex": block["header"].hex(),
                    "target_hex": "00" * 32,  # unreachable target: every nonce is hashed
                    "start_nonce": 1_000_000,
                    "count": count,
                },
            )
            assert result.output["checked"] == count
            rows.append(
                {
                    "nonces": count,
                    "wall_s": round(wall, 3),
                    "verified_hashes_per_s": round(count / wall),
                    "verification": result.receipt["verification"]["verdict"],
                }
            )
        # raw single-core hashlib baseline for context (no runtime, no verification)
        n = 200_000
        prefix = block["header"][:76]
        t0 = time.perf_counter()
        for nonce in range(n):
            sha256d(prefix + nonce.to_bytes(4, "little"))
        raw = n / (time.perf_counter() - t0)
        return {"chronus_submit_path": rows, "raw_hashlib_single_core_hashes_per_s": round(raw)}

    # --- PYTHIA production route on a real block ---------------------------------------------
    def production_route(self, blocks: dict) -> list[dict]:
        pre = precompute_pythia_search()
        rows = []
        for name, block in blocks.items():
            window = 1200
            base = block["nonce"] - 700
            hasher = ChronusVirtualIGPUHasher(
                client=ChronusClient(
                    daemon=RuntimeDaemon(
                        adapters=[CPUEmulatorAdapter()], store_dir=self.tmp / f"route-{name}"
                    )
                )
            )
            plan = SearchPlan(
                job_fingerprint=f"probe-{name}",
                pool_session_id="probe",
                generation=1,
                base_step=base,
                window=window,
                extranonce2="00000000",
                lane_order=tuple(range(32)),
                preferred_face=0,
                dispatch_breadth=window,
                executor_route="chronus_batch",
                policy_id="probe",
                evidence_refs={"search_architecture": SEARCH_ARCHITECTURE_ID},
                created_at=time.monotonic(),
                plan_id=f"plan-{name}",
                nonce_order=NONCE_ORDER_HENDRIX,
            )
            lease = NonceLease(
                lease_id=plan.plan_id,
                generation=1,
                plan_id=plan.plan_id,
                start=base,
                count=window,
            )

            def cpu(*_a):
                raise AssertionError("cpu oracle must not run the chronus_batch route")

            router = ProductionExecutionRouter(hasher, cpu, pythia_precompute=pre)
            target_le = block["target"].to_bytes(32, "little")
            t0 = time.perf_counter()
            record, candidate = router.execute_plan(plan, block["header"], target_le, lease=lease)
            wall = time.perf_counter() - t0
            rows.append(
                {
                    "block": name,
                    "window": window,
                    "route": record.executed_route,
                    "evidence_class": record.evidence_class.value,
                    "completion_state": record.completion_state.value,
                    "candidate_nonce": candidate["nonce"] if candidate else None,
                    "is_the_real_block_nonce": bool(
                        candidate and candidate["nonce"] == block["nonce"]
                    ),
                    "candidate_host_verified": bool(
                        candidate and candidate["independently_rechecked"]
                    ),
                    "hashes_before_hit": record.hash_count,
                    "wall_s": round(wall, 3),
                }
            )
        return rows

    # --- other workload kinds -----------------------------------------------------------------
    def numeric_and_data(self, blocks: dict) -> dict:
        import base64

        import numpy as np

        out: dict = {}
        # Lucas / Pisot / Phi
        for kind, n in (
            (WorkloadKind.LUCAS_TRANSFORM, 10_000),
            (WorkloadKind.PISOT_TRANSFORM, 10_000),
            (WorkloadKind.PHI_TRANSFORM, 1474),
        ):
            result, wall = self.submit(kind, {"n": n})
            out[kind.value] = {
                "n": n,
                "status": result.status,
                "verification": result.receipt["verification"]["verdict"],
                "wall_ms": round(wall * 1000, 2),
            }
        # Fold / unfold on real bytes (this repo's README + all three real headers)
        real_bytes = (REPO / "chronus" / "README.md").read_bytes() + b"".join(
            b["header"] for b in blocks.values()
        )
        result, wall = self.submit(
            WorkloadKind.FOLD, {"payload_b64": base64.b64encode(real_bytes).decode()}
        )
        fold = {
            "input_bytes": len(real_bytes),
            "status": result.status,
            "engine": result.output.get("engine"),
            "folded_bytes": result.output.get("folded_bytes"),
            "ratio": round(result.output.get("folded_bytes", 0) / len(real_bytes), 4),
            "verification": result.receipt["verification"]["verdict"],
            "wall_ms": round(wall * 1000, 2),
        }
        try:
            back, _ = self.submit(WorkloadKind.UNFOLD, {"folded_b64": result.output["folded_b64"]})
            fold["unfold_status"] = back.status
            payload = back.output.get("payload_b64")
            fold["roundtrip_exact"] = (
                base64.b64decode(payload) == real_bytes if payload is not None else None
            )
        except Exception as exc:
            fold["unfold_status"] = f"{type(exc).__name__}: {exc}"
        out["fold_real_bytes"] = fold
        # Store / retrieve a real header
        stored, _ = self.submit(
            WorkloadKind.STORE,
            {"payload_b64": base64.b64encode(blocks["genesis_h0"]["header"]).decode()},
        )
        out["store_retrieve"] = {
            "store_status": stored.status,
            "object_id_present": bool(stored.object_id),
        }
        # Dense numeric kernels: SYNTHETIC seeded data (no real dataset is shipped)
        rng = np.random.default_rng(20261006)
        sizes = (64, 256) if self.quick else (64, 256, 512)
        mats = []
        for n in sizes:
            a = rng.standard_normal((n, n))
            b = rng.standard_normal((n, n))
            result, wall = self.submit(
                WorkloadKind.TENSOR_OP, {"op": "matmul", "a": a.tolist(), "b": b.tolist()}
            )
            err = float(np.max(np.abs(np.asarray(result.output["data"]) - a @ b)))
            flops = 2 * n**3
            mats.append(
                {
                    "n": n,
                    "status": result.status,
                    "verification": result.receipt["verification"]["verdict"],
                    "max_abs_err_vs_numpy": err,
                    "wall_ms": round(wall * 1000, 2),
                    "end_to_end_gflops": round(flops / wall / 1e9, 4),
                }
            )
        out["tensor_matmul_synthetic_float64"] = mats
        a = rng.standard_normal((128, 128)) + 1j * rng.standard_normal((128, 128))
        x = rng.standard_normal(128) + 1j * rng.standard_normal(128)
        result, wall = self.submit(
            WorkloadKind.CGEMV,
            {"a": a.tolist(), "x": x.tolist()},
        )
        out["cgemv_128_synthetic_complex128"] = {
            "status": result.status,
            "verification": result.receipt["verification"]["verdict"],
            "wall_ms": round(wall * 1000, 2),
        }
        return out

    # --- runtime guarantees -------------------------------------------------------------------
    def runtime_guarantees(self) -> dict:
        out: dict = {}
        # receipt binding + latency of the cheapest workload
        lat = []
        last = None
        for _ in range(50 if self.quick else 200):
            result, wall = self.submit(WorkloadKind.PROBE, {})
            lat.append(wall)
            last = result
        lat.sort()
        out["probe_workload_latency_ms"] = {
            "n": len(lat),
            "median": round(statistics.median(lat) * 1000, 3),
            "p95": round(lat[int(len(lat) * 0.95) - 1] * 1000, 3),
        }
        report = validate_receipt(
            last.receipt,
            expect={
                "workload_id": last.workload_id,
                "actual_backend": "cpu-emulator",
                "protocol_version": "virtual_igpu_v1",
            },
        )
        out["receipt_identity_binding_ok"] = report["ok"]
        reloaded = RuntimeDaemon(adapters=[CPUEmulatorAdapter()], store_dir=self.daemon.root)
        out["evidence_ledger_records_reloaded"] = len(reloaded.ledger.list_records())
        # THESEUS custody commit latency (real HMAC-authenticated file custody)
        try:
            from hyba_db.theseus_custody import TheseusFileCustody

            custody = TheseusFileCustody(root=self.tmp / "custody", hmac_key=bytes(range(32)))
            d = RuntimeDaemon(
                adapters=[CPUEmulatorAdapter()], store_dir=self.tmp / "rt-custody", custody=custody
            )
            c = ChronusClient(daemon=d)
            times = []
            for i in range(20):
                wl = Workload(
                    id=f"custody-{i}",
                    kind=WorkloadKind.PROBE,
                    tenant="probe",
                    constraints={"custody": "required"},
                    execution_policy=ExecutionPolicy.STANDALONE_SOFTWARE.value,
                )
                t0 = time.perf_counter()
                r = c.submit(wl)
                times.append(time.perf_counter() - t0)
                assert r.metrics["custody"]["state"] == "committed"
            out["theseus_custody_commit_ms"] = {
                "n": len(times),
                "median": round(statistics.median(times) * 1000, 2),
            }
            custody.close()
        except Exception as exc:  # reported, never hidden
            out["theseus_custody_commit_ms"] = f"unavailable: {type(exc).__name__}: {exc}"
        return out

    # --- Chronus's own measurement harness ----------------------------------------------------
    def builtin_measurement(self) -> dict:
        try:
            from chronus.measurement.run import measure_chronus

            artifact, availability = measure_chronus(quick=True)
            return {"stages_available": availability}
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=None)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()

    blocks = verified_blocks()
    probe = Probe(args.quick)
    host = host_info()
    artifact = {
        "schema": "chronus.capability_probe/2",
        "generated_at_unix": int(time.time()),
        "host": host,
        "product_modes": {
            ProductMode.NATIVE_CHRONUS_GPU.value: {
                "selected": True,
                "available": True,
                "physical_gpu_required": False,
                "execution_policy": ExecutionPolicy.STANDALONE_SOFTWARE.value,
                "observed_execution_substrate": "cpu-emulator",
                "note": (
                    "Chronus is the GPU product in this mode; cpu-emulator is the "
                    "observed host execution substrate, not product identity"
                ),
            },
            ProductMode.HOST_GPU_AUGMENTATION.value: {
                "selected": False,
                "available": None,
                "physical_gpu_required": True,
                "execution_policy": ExecutionPolicy.PREFERRED_ACCELERATOR.value,
                "note": (
                    "not exercised by this CPU-reference probe; host-GPU/accelerator "
                    "augmentation requires separate device-bound certification"
                ),
            },
        },
        "real_data": {
            n: {"block_hash": b["block_hash"], "bits": hex(b["bits"]), "nonce": b["nonce"]}
            for n, b in blocks.items()
        },
        "adapters_available": [a.id for a in probe.daemon.adapters if a.available],
        "sha256d_real_blocks": probe.sha256d_correctness(blocks),
        "sha256d_throughput": probe.sha256d_throughput(blocks["block_h125552"]),
        "production_route_real_blocks": probe.production_route(blocks),
        "workload_kinds": probe.numeric_and_data(blocks),
        "runtime_guarantees": probe.runtime_guarantees(),
        "builtin_measurement_harness": probe.builtin_measurement(),
        "claims_not_made": [
            "physical GPU/accelerator execution or performance unless separately certified",
            "hardware-rooted attestation",
            "multi-core or fleet throughput (single process, single adapter)",
            "pool acknowledgement / accepted share",
            "the governed 1e19 H/s engineering ceiling",
        ],
    }
    text = json.dumps(artifact, indent=2, default=str)
    if args.out:
        Path(args.out).write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

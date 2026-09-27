"""Super-GPU benchmark — measured per-device paths, honest on bare hosts.

Runs the composed-substrate view against the synthetic header corpus:

  (a) per-device       — every device in the inventory, measured alone
  (b) aggregate        — MultiDeviceHasher Lucas partition across all devices
  (c) best_single      — the fastest member alone
  (d) composed_ops     — SuperGPU.execute on the IR ops that can run here

Metrics: measured hashes/sec per device, wall ns, partition efficiency
(aggregate / sum-of-members), attestation coverage. On a host with no
measured GPU/ASIC every claim is emitted as ``{"measured": false, ...}``
— the harness never fabricates a number it did not measure.

Usage: python scripts/benchmark_super_gpu.py --n 8 --nonce-space 4096
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parent.parent / "mla1517_platform_v3.4" / "python"
    ),
)

import numpy as np

from hyba.attestation import AttestationLog
from hyba.inventory import ClusterInventory
from hyba.multi_hasher import MultiDeviceHasher
from hyba.virtual_gpu import SuperGPU

REPORTS = Path(__file__).resolve().parent.parent / "reports"
CORPUS_SEED = 0x53555047


def synthetic_headers(n: int, seed: int = CORPUS_SEED) -> List[bytes]:
    out = []
    for i in range(n):
        h = hashlib.sha256(struct_pack(seed, i)).digest()
        out.append(h + hashlib.sha256(h).digest() + h[:16])
    return out


def struct_pack(a: int, b: int) -> bytes:
    import struct

    return struct.pack("<QQ", a & 0xFFFFFFFFFFFFFFFF, b & 0xFFFFFFFFFFFFFFFF)


def easy_target(bits_hi: int = 248) -> bytes:
    """A target every window hits — top byte of the LE digest < 1/128."""
    return (2**bits_hi - 1).to_bytes(32, "big")


def measure_device(hasher, headers, target, window) -> Dict[str, Any]:
    """Grind `window` nonces per header on one hasher; measured hps."""
    hashes = 0
    t0 = time.perf_counter()
    winners = 0
    for header in headers:
        _, _, h = hasher.grind_target_range(header, target, 0, window)
        hashes += h
    wall = time.perf_counter() - t0
    _ = winners
    return {
        "hashes": hashes,
        "wall_s": wall,
        "hashes_per_s": hashes / wall if wall > 0 else 0.0,
        "backend": hasher.backend,
        "device": hasher.device,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=8, help="headers in corpus")
    ap.add_argument("--nonce-space", type=int, default=4096)
    ap.add_argument("--out", type=Path, default=REPORTS / "super_gpu_benchmark.json")
    args = ap.parse_args()

    REPORTS.mkdir(exist_ok=True)
    headers = synthetic_headers(args.n)
    target = easy_target()
    window = args.nonce_space

    inventory = ClusterInventory.collect()
    super_gpu = SuperGPU.compose(inventory)
    AttestationLog.reset()

    report: Dict[str, Any] = {
        "benchmark": "super_gpu",
        "corpus": {"kind": "synthetic", "headers": args.n, "seed": CORPUS_SEED},
        "nonce_space": window,
        "inventory": inventory.as_dict(),
        "composed": super_gpu.as_dict(),
    }

    # (a) per-device measured paths — only devices that can actually run.
    from mining.bitcoin_hasher import BitcoinHasher

    per_device: List[Dict[str, Any]] = []
    members: List[Any] = []
    for dev in inventory.devices:
        if dev.backend not in ("opencl", "cpu"):
            continue  # asic/rtl listed but not runnable in this harness
        try:
            hasher = BitcoinHasher(device=dev.name) if dev.backend == "opencl" else BitcoinHasher(backend="cpu")
        except Exception as exc:
            per_device.append(
                {"device": dev.name, "measured": False, "reason": str(exc)}
            )
            continue
        measured = measure_device(hasher, headers, target, window)
        per_device.append({"measured": True, **measured})
        members.append(hasher)

    # (b) aggregate — Lucas partition across every runnable member.
    if len(members) > 1:
        pool = MultiDeviceHasher(members, include_cpu=False)
        agg_hashes = 0
        t0 = time.perf_counter()
        for header in headers:
            r = pool.grind_target_range(header, target, 0, window)
            agg_hashes += r["hashes"]
        agg_wall = time.perf_counter() - t0
        aggregate = {
            "measured": True,
            "hashes": agg_hashes,
            "wall_s": agg_wall,
            "hashes_per_s": agg_hashes / agg_wall if agg_wall > 0 else 0.0,
            "members": pool.telemetry()["members"],
        }
    else:
        aggregate = {"measured": False, "reason": "fewer than 2 runnable devices"}

    # (c) best single = the fastest measured member.
    measured_devices = [d for d in per_device if d.get("measured")]
    best_single = (
        max(measured_devices, key=lambda d: d["hashes_per_s"])
        if measured_devices
        else {"measured": False, "reason": "no measured device"}
    )

    # (d) composed IR ops — executed on whatever the inventory has.
    composed_ops: Dict[str, Any] = {}
    for op, inputs in (
        ("cnormsq", {"in_float": np.arange(11, dtype=np.float32) * 0.1}),
        ("lucas_pisot_scale", {"scale_index": 20, "kind": "lucas"}),
        (
            "sha256d_scan",
            {
                "header": headers[0][:76],
                "base_nonce": 0,
                "count": min(window, 256),
                "target": int.from_bytes(target, "big"),
            },
        ),
    ):
        try:
            result = super_gpu.execute(op, inputs, {"work_items": window})
            composed_ops[op] = {
                "measured": result.truth_class == "measured",
                "truth_class": result.truth_class,
                "backend": result.backend,
                "device": result.device_name,
                "measured_ns": result.measured_ns,
                "attestation": result.attestation.as_dict(),
            }
        except Exception as exc:
            composed_ops[op] = {"measured": False, "reason": str(exc)}

    # Partition efficiency = aggregate / sum-of-member rates.
    total_member_rate = sum(d["hashes_per_s"] for d in measured_devices)
    efficiency = (
        aggregate["hashes_per_s"] / total_member_rate
        if aggregate.get("measured") and total_member_rate > 0
        else None
    )

    report.update(
        {
            "per_device": per_device,
            "aggregate": aggregate,
            "best_single": best_single,
            "partition_efficiency": efficiency,
            "composed_ops": composed_ops,
            "attestation_summary": AttestationLog.get().summary(),
            "verdict": {
                "measured_gpu_present": any(
                    d.get("measured") and "opencl" in d.get("backend", "")
                    for d in per_device
                ),
                "aggregate_measured": bool(aggregate.get("measured")),
            },
        }
    )
    args.out.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report["verdict"], indent=2))
    print(f"report -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

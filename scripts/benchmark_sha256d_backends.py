"""SHA-256d backend benchmark — the same work units on every lane.

Runs the identical header/target/windows through each requested hasher
lane — ``cpu`` (the labelled hashlib reference), ``opencl``, ``cuda`` and
``metal`` (the Chronus-owned native lanes in ``mining.native_sha256d``) —
and reports measured throughput plus a cross-lane parity check: every lane
that answers must produce the *identical* winner nonce and digest, since
host-side hashlib is the sole accept authority everywhere.

Honesty contract:

* A lane is probed by binding its hasher (which runs the bind-time
  hashlib self-check battery). If binding fails the lane is reported
  ``{"measured": false, "reason": ...}`` — never skipped silently and
  never substituted.
* Numbers are wall-clock measured on the caller plus the lane's own
  telemetry (kernel clock source is labelled — ``cl_event``,
  ``cuda_event`` or ``perf_counter`` — since they are not the same clock).
* A parity violation (two lanes disagree on winner/digest for the same
  work unit) exits nonzero: that is a correctness alarm, not a slowdown.

Work units, all on one fixed header and a target with a guaranteed hit
~75% through each window:

* ``digest_batch``  — ``hash_batch`` over explicit nonces; parity is exact
  digest equality.
* ``range``         — ``grind_target_range`` contiguous scan.
* ``m32``           — ``grind_target_m32`` Turing lane-ordered scan.
* ``hendrix``       — ``grind_target_hendrix`` coprime-stride schedule.
* ``gold``          — ``grind_target_gold`` golden-stride walk.

Usage:

    python scripts/benchmark_sha256d_backends.py
    python scripts/benchmark_sha256d_backends.py --lanes cpu opencl --batch 262144 --repeat 2
    python scripts/benchmark_sha256d_backends.py --json-out reports/sha256d-bench.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "chronus/mla1517_platform" / "python"))

SCHEMA = "phiminer.sha256d_backend_benchmark/1"
LANES = ("cpu", "opencl", "cuda", "metal")
GOLDEN_STRIDE = 0x9E3779B9  # floor(2^32/phi); odd -> coprime with any 2^k window
MAX_BATCH = 65536


def _sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def _header(seed: int) -> bytes:
    """Deterministic 80-byte header for the run."""
    out = b""
    for i in range(3):
        out += _sha256d(struct.pack("<QQ", seed, i))[:32]
    return out[:80]


def _nonce_bytes(nonce: int) -> bytes:
    return struct.pack("<I", nonce & 0xFFFFFFFF)


def _digest_le(header: bytes, nonce: int) -> bytes:
    return _sha256d(header + _nonce_bytes(nonce))


def _target_for_hit(header: bytes, nonce: int) -> bytes:
    """Big-endian target equal to the little-endian digest at ``nonce`` —
    guarantees at least one hit in any window containing that nonce."""
    return _digest_le(header, nonce)[::-1]


def _m32_lane_order(base_nonce: int) -> tuple:
    from chronus.mla1517.mining.solver import M32SearchSolver

    return M32SearchSolver().turing.lane_order(base_nonce)


def _m32_nonce(base_nonce: int, lane_order, step: int) -> int:
    return (base_nonce + lane_order[step % 32] + 32 * (step // 32)) & 0xFFFFFFFF


def _gold_nonce(seed: int, step: int) -> int:
    return (seed + step * GOLDEN_STRIDE) & 0xFFFFFFFF


def _hendrix_nonce(base: int, window: int, stride: int, position: int) -> int:
    return (base + (position * stride) % window) & 0xFFFFFFFF


def _work_units(header: bytes, batch: int) -> List[Dict[str, Any]]:
    """Deterministic work-unit descriptors shared by every lane."""
    lane_order = _m32_lane_order(0)
    m32_count = (batch // 32) * 32
    gold_seed = (
        struct.unpack(
            "<I", hashlib.sha256(b"gold-stride-v1|" + header + b"\xff" * 32).digest()[:4]
        )[0]
    )
    units: List[Dict[str, Any]] = [
        {
            "id": "digest_batch",
            "kind": "digest_batch",
            "scanned": min(batch, MAX_BATCH),
            "nonces": list(range(min(batch, MAX_BATCH))),
            "target": None,
        },
        {
            "id": "range",
            "kind": "range",
            "scanned": batch,
            "base_nonce": 0,
            "count": batch,
            "hit_step": (batch * 3) // 4,
            "target": _target_for_hit(header, (batch * 3) // 4),
        },
        {
            "id": "m32",
            "kind": "m32",
            "scanned": m32_count,
            "base_nonce": 0,
            "count": m32_count,
            "lane_order": lane_order,
            "hit_step": (m32_count * 3) // 4,
            "target": _target_for_hit(header, _m32_nonce(0, lane_order, (m32_count * 3) // 4)),
        },
        {
            "id": "hendrix",
            "kind": "hendrix",
            "scanned": batch,
            "base_nonce": 0,
            "window": batch,
            "stride": GOLDEN_STRIDE,
            "position": 0,
            "count": batch,
            "hit_step": (batch * 3) // 4,
            "target": _target_for_hit(
                header, _hendrix_nonce(0, batch, GOLDEN_STRIDE, (batch * 3) // 4)
            ),
        },
        {
            "id": "gold",
            "kind": "gold",
            "scanned": batch,
            "seed": gold_seed,
            "count": batch,
            "hit_step": (batch * 3) // 4,
            "target": _target_for_hit(header, _gold_nonce(gold_seed, (batch * 3) // 4)),
        },
    ]
    return units


def _run_unit(hasher, unit: Dict[str, Any]) -> Tuple[Any, Any, int]:
    """Execute one timed launch; returns (winner_nonce, digest, hashes)."""
    kind = unit["kind"]
    if kind == "digest_batch":
        digests = hasher.hash_batch(_WORK_HEADER, unit["nonces"])
        return unit["nonces"], digests, len(unit["nonces"])
    if kind == "range":
        n, d, h = hasher.grind_target_range(
            _WORK_HEADER, unit["target"], unit["base_nonce"], unit["count"]
        )
        return n, d, h
    if kind == "m32":
        n, d, h = hasher.grind_target_m32(
            _WORK_HEADER, unit["target"], unit["base_nonce"], unit["lane_order"], unit["count"]
        )
        return n, d, h
    if kind == "hendrix":
        n, d, h = hasher.grind_target_hendrix(
            _WORK_HEADER,
            unit["target"],
            unit["base_nonce"],
            unit["window"],
            unit["stride"],
            unit["position"],
            unit["count"],
        )
        return n, d, h
    if kind == "gold":
        n, d, h, _fifo = hasher.grind_target_gold(
            _WORK_HEADER, unit["target"], unit["count"], seed=unit["seed"]
        )
        return n, d, h
    raise AssertionError(f"unknown work unit {kind}")


_WORK_HEADER = b""


def _bench_unit(hasher, unit: Dict[str, Any], warmup: int, repeat: int) -> Dict[str, Any]:
    """Warmup then timed launches; wall clock is authoritative."""
    telemetry = hasher.telemetry()
    kernel_before = telemetry.get("kernel_ms", 0.0)
    launches_before = telemetry.get("launches", 0)
    for _ in range(warmup):
        _run_unit(hasher, unit)
    walls: List[float] = []
    last: Tuple[Any, Any, int] = (None, None, 0)
    for _ in range(repeat):
        t0 = time.perf_counter()
        last = _run_unit(hasher, unit)
        walls.append(time.perf_counter() - t0)
    telemetry = hasher.telemetry()
    kernel_ms = max(0.0, float(telemetry.get("kernel_ms", 0.0)) - float(kernel_before))
    launches = int(telemetry.get("launches", 0)) - int(launches_before)
    wall_s = sum(walls)
    scanned = int(last[2])
    winner_nonce, winner_digest = last[0], last[1]
    if isinstance(winner_digest, list):
        # digest_batch parity payload: one hash over the whole digest list —
        # exact-equality evidence without embedding 64K digests in the JSON.
        parity_key = {
            "count": len(winner_digest),
            "digest_chain_sha256": hashlib.sha256(
                b"".join(d if isinstance(d, (bytes, bytearray)) else bytes(d) for d in winner_digest)
            ).hexdigest(),
        }
    else:
        parity_key = {
            "winner_nonce": winner_nonce,
            "winner_digest": winner_digest.hex() if isinstance(winner_digest, (bytes, bytearray)) else winner_digest,
        }
    return {
        "measured": True,
        "launches": launches,
        "scanned_per_launch": scanned,
        "scanned_total": scanned * repeat,
        "wall_s": round(wall_s, 6),
        "hashes_per_s": (scanned * repeat / wall_s) if wall_s > 0 else None,
        "kernel_ms": round(kernel_ms, 3),
        "kernel_clock_source": telemetry.get("clock_source"),
        "winner_nonce": winner_nonce if not isinstance(winner_nonce, list) else None,
        "parity": parity_key,
        "min_wall_s": round(min(walls), 6),
        "max_hashes_per_s": (scanned / min(walls)) if min(walls) > 0 else None,
    }


def _bind_lane(lane: str) -> Dict[str, Any]:
    from mining.bitcoin_hasher import hasher_for_backend

    try:
        hasher = hasher_for_backend(lane)
    except Exception as exc:
        return {"lane": lane, "measured": False, "reason": str(exc), "hasher": None}
    status = hasher.silicon_status()
    return {
        "lane": lane,
        "measured": True,
        "backend": hasher.backend,
        "device": hasher.device,
        "opencl_required": status.get("opencl_required", lane in ("opencl", "gpu", "cpu")),
        "kernel_clock_source": hasher.telemetry().get("clock_source"),
        "hasher": hasher,
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark the SHA-256d lanes on identical work units.",
    )
    parser.add_argument("--lanes", nargs="+", choices=LANES, default=list(LANES))
    parser.add_argument("--batch", type=int, default=1 << 20,
                        help="nonces scanned per grind launch (default 1<<20)")
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--header-seed", type=int, default=0xC4102,
                        help="seed for the shared deterministic header")
    parser.add_argument("--json-out", type=Path, default=None,
                        help="artifact path (default reports/sha256d-backend-benchmark-<utc>.json)")
    args = parser.parse_args(argv)

    global _WORK_HEADER
    _WORK_HEADER = _header(args.header_seed)
    units = _work_units(_WORK_HEADER, args.batch)

    report: Dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "parameters": {
            "batch": args.batch,
            "warmup": args.warmup,
            "repeat": args.repeat,
            "header_seed": args.header_seed,
            "header_sha256": hashlib.sha256(_WORK_HEADER).hexdigest(),
        },
        "work_units": [
            {k: (v.hex() if isinstance(v, bytes) else v)
             for k, v in u.items() if k not in ("nonces", "lane_order")}
            for u in units
        ],
        "lanes": {},
        "parity": {},
    }

    bound: Dict[str, Any] = {}
    for lane in args.lanes:
        entry = _bind_lane(lane)
        bound[lane] = entry.pop("hasher", None)
        report["lanes"][lane] = entry
        tag = "bound" if entry["measured"] else "unavailable"
        detail = entry.get("device") or entry.get("reason") or ""
        print(f"[{tag:>11}] {lane:>6}  {detail}")

    measured_lanes = [l for l in args.lanes if bound[l] is not None]
    if not measured_lanes:
        print("no lanes measured — nothing to compare (see reasons above)")

    for unit in units:
        parity_ref: Optional[Dict[str, Any]] = None
        unit_parity: Dict[str, Any] = {"consistent": True, "lanes": {}}
        for lane in measured_lanes:
            try:
                result = _bench_unit(bound[lane], unit, args.warmup, args.repeat)
            except Exception as exc:
                result = {"measured": False, "reason": str(exc)}
                unit_parity["consistent"] = False
            report["lanes"][lane].setdefault("results", {})[unit["id"]] = result
            unit_parity["lanes"][lane] = result.get("parity")
            if result.get("measured"):
                if parity_ref is None:
                    parity_ref = result["parity"]
                elif result["parity"] != parity_ref:
                    unit_parity["consistent"] = False
        report["parity"][unit["id"]] = unit_parity

    print()
    header_row = f"{'work unit':<14} {'scanned':>10}"
    for lane in measured_lanes:
        header_row += f" {lane:>16}"
    print(header_row)
    print("-" * len(header_row))
    for unit in units:
        row = f"{unit['id']:<14} {unit['scanned']:>10}"
        for lane in measured_lanes:
            r = report["lanes"][lane].get("results", {}).get(unit["id"], {})
            hps = r.get("max_hashes_per_s")
            row += f" {('%s' % _fmt_rate(hps)) if hps else 'unmeasured':>16}"
        parity_mark = "" if report["parity"][unit["id"]]["consistent"] else "  PARITY VIOLATION"
        print(row + parity_mark)
    print()
    print("hashes/s is the best timed launch's wall-clock rate; kernel clock")
    print("sources differ per lane (cl_event / cuda_event / perf_counter).")

    out = args.json_out
    if out is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = _REPO_ROOT / "reports" / f"sha256d-backend-benchmark-{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(_jsonable(report), indent=2) + "\n", encoding="utf-8")
    print(f"artifact: {out}")

    if not all(p["consistent"] for p in report["parity"].values()):
        print("PARITY VIOLATION: lanes disagree on a winner/digest — correctness alarm")
        return 2
    return 0


def _fmt_rate(hps: Optional[float]) -> str:
    if hps is None:
        return ""
    for unit, scale in (("GH/s", 1e9), ("MH/s", 1e6), ("KH/s", 1e3)):
        if hps >= scale:
            return f"{hps / scale:.2f} {unit}"
    return f"{hps:.0f} H/s"


if __name__ == "__main__":
    raise SystemExit(main())

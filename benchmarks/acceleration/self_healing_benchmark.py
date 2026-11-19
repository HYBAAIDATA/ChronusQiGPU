#!/usr/bin/env python3
"""Measured THESEUS self-healing performance (Reed-Solomon RS(48,32) over GF(257)).

Every number comes from timing the real code on this machine: the durable
SQLite store, the batched numpy decoder and, for comparison, the pure-Python
Berlekamp-Welch reference decoder (``reed_solomon.decode_block``) that the
store used before the batched decoder. Faults are injected by rewriting bytes
in the SQLite file. Every repaired result is checked byte-for-byte and against
its SHA-256 content address; a mismatch aborts the run.

Payloads are deterministic SHA-256 counter streams (incompressible, no
structure the decoder could exploit).

    python benchmarks/acceleration/self_healing_benchmark.py \
        --out benchmarks/acceleration/self_healing_raw.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from chronus.security.al_haras import reed_solomon as rs  # noqa: E402
from chronus.storage import self_heal  # noqa: E402
from chronus.storage.durable import DurableTheseusService  # noqa: E402

# Pin inline THESEUS repair so measurements do not depend on CHRONUS_SELF_HEALING_REPAIR.
_INLINE = {"self_healing": True, "repair_authority": "theseus"}

KIB = 1024


def payload_of(size: int, seed: str = "theseus") -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < size:
        out += hashlib.sha256(f"{seed}:{counter}".encode()).digest()
        counter += 1
    return bytes(out[:size])


def worst_case_positions(size: int, per_block: int = 8) -> list[int]:
    """``per_block`` damaged bytes in every 32-byte block (the correction bound)."""
    return [b + i * 4 for b in range(0, size, 32) for i in range(per_block) if b + i * 4 < size]


def corrupt(path: Path, object_id: str, positions) -> None:
    with closing(sqlite3.connect(path)) as db, db:
        (blob,) = db.execute("SELECT payload FROM objects WHERE object_id=?", (object_id,)).fetchone()
        damaged = bytearray(blob)
        for p in positions:
            damaged[p] ^= 0x5A
        db.execute("UPDATE objects SET payload=? WHERE object_id=?", (bytes(damaged), object_id))


def stats(samples_s: list[float]) -> dict:
    ms = sorted(s * 1000 for s in samples_s)
    return {
        "count": len(ms),
        "median_ms": round(statistics.median(ms), 3),
        "p95_ms": round(ms[min(len(ms) - 1, int(0.95 * len(ms)))], 3),
        "min_ms": round(ms[0], 3),
        "max_ms": round(ms[-1], 3),
    }


def timed(fn, repeat: int) -> list[float]:
    out = []
    for _ in range(repeat):
        t = time.perf_counter()
        fn()
        out.append(time.perf_counter() - t)
    return out


def reference_heal(received: bytes, parity: np.ndarray) -> bytes:
    """Pre-acceleration path: Berlekamp-Welch per block in pure Python."""
    out = bytearray()
    k = rs.DEFAULT_K
    for b, start in enumerate(range(0, len(received), k)):
        chunk = list(received[start:start + k])
        pad = k - len(chunk)
        res = rs.decode_block(chunk + [0] * pad + parity[b].tolist(), rs.DEFAULT_N, k)
        out += bytes(res["data"][: k - pad])
    return bytes(out)


def bench_codec(sizes, repeat_fast: int, reference: bool) -> dict:
    result = {}
    for size in sizes:
        data = payload_of(size)
        oid = hashlib.sha256(data).hexdigest()
        parity_blob = self_heal.encode_parity(data)
        parity = rs.encode_blocks(data)
        bad = bytearray(data)
        for p in worst_case_positions(size):
            bad[p] ^= 0x5A
        bad = bytes(bad)
        outcome = self_heal.heal_payload(bad, oid, parity_blob, size)
        assert outcome.repaired == data, "batched decoder lost exactness"
        row = {
            "encode_batched": stats(timed(lambda: self_heal.encode_parity(data), repeat_fast)),
            "verify_healthy_batched": stats(timed(lambda: self_heal.heal_payload(data, oid, parity_blob, size), repeat_fast)),
            "repair_worst_case_batched": stats(timed(lambda: self_heal.heal_payload(bad, oid, parity_blob, size), repeat_fast)),
            "corrected_bytes": len(outcome.corrected_positions),
        }
        if reference:
            t = time.perf_counter()
            ref = reference_heal(bad, parity)
            row["repair_worst_case_reference_s"] = round(time.perf_counter() - t, 3)
            assert ref == data, "reference decoder disagrees"
            row["speedup_worst_case"] = round(
                row["repair_worst_case_reference_s"] * 1000 / row["repair_worst_case_batched"]["median_ms"], 1)
        result[f"{size // KIB}KiB"] = row
    return result


def bench_store(workdir: Path, sizes, repeat: int) -> dict:
    result = {}
    for size in sizes:
        data = payload_of(size, f"store-{size}")
        path = workdir / f"store-{size}.sqlite3"
        store = DurableTheseusService(str(path), **_INLINE)
        rec = store.store("tenant-a", data)
        healthy = timed(lambda: store.reconstruct("tenant-a", rec.object_id), repeat)
        strict = DurableTheseusService(str(path), self_healing=False)
        healthy_strict = timed(lambda: strict.reconstruct("tenant-a", rec.object_id), repeat)
        corrupted = []
        light = []
        for _ in range(max(3, repeat // 10)):
            corrupt(path, rec.object_id, worst_case_positions(size))
            t = time.perf_counter()
            got = store.reconstruct("tenant-a", rec.object_id)
            corrupted.append(time.perf_counter() - t)
            assert got == data
            corrupt(path, rec.object_id, [size // 2])
            t = time.perf_counter()
            got = store.reconstruct("tenant-a", rec.object_id)
            light.append(time.perf_counter() - t)
            assert got == data
        result[f"{size // KIB}KiB"] = {
            "healthy_read_self_healing_on": stats(healthy),
            "healthy_read_self_healing_off": stats(healthy_strict),
            "corrupted_read_worst_case": stats(corrupted),
            "corrupted_read_one_byte": stats(light),
        }
    return result


def bench_startup(workdir: Path, objects: int, size: int, damaged: int) -> dict:
    path = workdir / "startup.sqlite3"
    store = DurableTheseusService(str(path), **_INLINE)
    recs = [store.store("tenant-a", payload_of(size, f"obj-{i}")) for i in range(objects)]
    t = time.perf_counter()
    DurableTheseusService(str(path), **_INLINE)
    clean = time.perf_counter() - t
    for rec in recs[:damaged]:
        corrupt(path, rec.object_id, worst_case_positions(size))
    t = time.perf_counter()
    reopened = DurableTheseusService(str(path), **_INLINE)
    recovery = time.perf_counter() - t
    for i, rec in enumerate(recs[:damaged]):
        assert reopened.reconstruct("tenant-a", rec.object_id) == payload_of(size, f"obj-{i}")
    return {
        "objects": objects,
        "object_bytes": size,
        "damaged_objects": damaged,
        "damage": "8 bytes in every 32-byte block of each damaged object",
        "open_clean_s": round(clean, 3),
        "open_with_recovery_s": round(recovery, 3),
        "repairs_recorded": reopened.self_healing_status()["repairs"],
    }


def _proc_read(args):
    path, oid = args
    t = time.perf_counter()
    DurableTheseusService(path, **_INLINE).reconstruct("tenant-a", oid)
    return time.perf_counter() - t


def bench_concurrent(workdir: Path, size: int, workers: int) -> dict:
    data = payload_of(size, "concurrent")
    out = {}
    # Threads: one store object, many readers of one damaged object.
    path = workdir / "concurrent-threads.sqlite3"
    store = DurableTheseusService(str(path), **_INLINE)
    rec = store.store("tenant-a", data)
    corrupt(path, rec.object_id, worst_case_positions(size))
    t = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        got = list(pool.map(lambda _: store.reconstruct("tenant-a", rec.object_id), range(workers * 4)))
    assert got == [data] * (workers * 4)
    out["threads"] = {"workers": workers, "reads": workers * 4, "wall_s": round(time.perf_counter() - t, 3),
                      "repairs_recorded": store.self_healing_status()["repairs"]}
    # Processes: separate interpreters opening the same damaged file.
    path = workdir / "concurrent-procs.sqlite3"
    store = DurableTheseusService(str(path), **_INLINE)
    rec = store.store("tenant-a", data)
    corrupt(path, rec.object_id, worst_case_positions(size))
    t = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        per = list(pool.map(_proc_read, [(str(path), rec.object_id)] * workers))
    out["processes"] = {"workers": workers, "wall_s": round(time.perf_counter() - t, 3),
                        "per_process_open_and_read": stats(per),
                        "repairs_recorded": DurableTheseusService(str(path), **_INLINE).self_healing_status()["repairs"]}
    return out


def hardware() -> dict:
    cpu = platform.processor() or ""
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[1].strip()
                break
    except OSError:
        pass  # /proc/cpuinfo is Linux-only; fall back to platform.processor()
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    except OSError:
        commit = ""
    return {
        "cpu": cpu, "logical_cpus": os.cpu_count(), "machine": platform.machine(),
        "os": platform.platform(), "python": platform.python_version(), "numpy": np.__version__,
        "sqlite": sqlite3.sqlite_version, "git_commit": commit,
        "accelerator": "none used (CPU numpy int64; OpenCL/CUDA tensor backends need a provisioned GPU)",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    parser.add_argument("--repeat", type=int, default=30)
    parser.add_argument("--no-reference", action="store_true", help="skip the slow pure-Python reference timings")
    args = parser.parse_args()
    sizes = [4 * KIB, 64 * KIB, 256 * KIB]
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        report = {
            "benchmark": "theseus-self-healing",
            "code": "RS(48,32) over GF(257), SHA-256 verified",
            "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "hardware": hardware(),
            "codec": bench_codec(sizes, args.repeat, not args.no_reference),
            "store_reads": bench_store(work, sizes, args.repeat),
            "startup_recovery": bench_startup(work, objects=200, size=64 * KIB, damaged=20),
            "concurrent_repair": bench_concurrent(work, 256 * KIB, workers=min(8, os.cpu_count() or 1)),
        }
    text = json.dumps(report, indent=2)
    if args.out:
        args.out.write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

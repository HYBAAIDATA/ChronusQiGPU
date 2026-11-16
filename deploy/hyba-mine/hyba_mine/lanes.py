"""SHA-256d nonce search across every execution lane of the mining host.

Two lane sets exist on a host:

* OpenCL iGPU lanes: the packaged kernel chronus/kernels/sha256d_search.cl run
  by chronus.execution.opencl_sha256d on every compute unit of the OpenCL
  device. On a host without a discrete GPU this is the CPU device, so the
  QiGPU runs in Mode A on CPU silicon.
* Process lanes: one operating-system process per available CPU, each running
  the host reference over its share of the window.

A lane set is used only after it qualifies on this host: its results must equal
the host reference on known-answer windows (the genesis block's nonce at
difficulty 1, an easy-target window on block 1 with several hits, and a target
no hash can meet). The host reference is itself checked against the published
hashes of blocks 0 and 1. Every hit a lane set reports is rechecked on the host
before use.
"""

from __future__ import annotations

import hashlib
import multiprocessing
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from chronus.execution.hashrate_cap import process_cap
from chronus.fleet.capacity import discover_host, rate_per_second

GENESIS_HEADER = bytes.fromhex(
    "01000000" + "00" * 32
    + "3ba3edfd7a7b12b27ac72c3e67768f617fc81bc3888a51323a9fb8aa4b1e5e4a"
    + "29ab5f49" + "ffff001d" + "1dac2b7c"
)
GENESIS_HASH = "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"
GENESIS_NONCE = 2083236893
BLOCK1_HEADER = bytes.fromhex(
    "01000000"
    + "6fe28c0ab6f1b372c1a6a246ae63f74f931e8365e15a089c68d6190000000000"
    + "982051fd1e4ba744bbbe680e1fee14677ba1a3c3540bf7b1cdb606e857233e0e"
    + "61bc6649" + "ffff001d" + "01e36299"
)
BLOCK1_HASH = "00000000839a8e6886ab5951d76f411475428afc90947ee320161bbf18eb6048"
DIFF1_TARGET = 0xFFFF << 208
MAX_NONCE = 1 << 32
_TOP_ZERO = b"\x00\x00\x00\x00"


class LaneUnavailable(RuntimeError):
    """A lane set is missing on this host or did not qualify."""


def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def reference_scan(header80: bytes, start: int, stop: int, target: int) -> List[int]:
    """Host reference: every nonce in [start, stop) whose SHA-256d meets target, ascending."""
    if not isinstance(header80, (bytes, bytearray)) or len(header80) != 80:
        raise ValueError("header must be exactly 80 bytes")
    if not 0 <= start <= stop <= MAX_NONCE:
        raise ValueError("nonce range must lie within [0, 2**32]")
    if not 0 <= target < 1 << 256:
        raise ValueError("target must be an unsigned 256-bit integer")
    prefix = bytes(header80[:76])
    sha256 = hashlib.sha256
    top_must_be_zero = target < 1 << 224
    hits = []
    for nonce in range(start, stop):
        digest = sha256(sha256(prefix + nonce.to_bytes(4, "little")).digest()).digest()
        if top_must_be_zero and digest[28:] != _TOP_ZERO:
            continue
        if int.from_bytes(digest, "little") <= target:
            hits.append(nonce)
    return hits


def split_range(start: int, stop: int, parts: int) -> List[Tuple[int, int]]:
    """Split [start, stop) into at most `parts` contiguous, disjoint, non-empty ranges."""
    if parts < 1:
        raise ValueError("parts must be positive")
    width = stop - start
    if width <= 0:
        return []
    parts = min(parts, width)
    size, extra = divmod(width, parts)
    ranges = []
    cursor = start
    for index in range(parts):
        end = cursor + size + (1 if index < extra else 0)
        ranges.append((cursor, end))
        cursor = end
    return ranges


class ProcessLanes:
    """One process per lane, each running the host reference on its share of a window."""

    name = "process-lanes"

    def __init__(self, lanes: int) -> None:
        if lanes < 1:
            raise ValueError("lanes must be positive")
        self.lanes = lanes
        self._pool = ProcessPoolExecutor(
            max_workers=lanes, mp_context=multiprocessing.get_context("spawn")
        )
        # Start every worker before any timing, so calibration measures hashing only.
        list(self._pool.map(reference_scan, [GENESIS_HEADER] * lanes, [0] * lanes,
                            [1] * lanes, [0] * lanes))

    def describe(self) -> Dict[str, Any]:
        return {"backend": self.name, "lanes": self.lanes, "processes": self.lanes}

    def search(self, header80: bytes, start: int, stop: int, target: int) -> List[int]:
        hits: List[int] = []
        cursor = start
        while cursor < stop:
            # Charge the process hash budget before dispatch; wait for it rather than skip nonces.
            granted = process_cap().allow(stop - cursor)
            if granted <= 0:
                time.sleep(max(process_cap().wait_ns(), 1_000_000) / 1_000_000_000)
                continue
            chunk_stop = cursor + granted
            chunks = split_range(cursor, chunk_stop, self.lanes)
            futures = [self._pool.submit(reference_scan, bytes(header80), a, b, target) for a, b in chunks]
            for future in futures:
                hits.extend(future.result())
            cursor = chunk_stop
        return hits

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


class OpenCLLanes:
    """The packaged SHA-256d kernel on every compute unit of the OpenCL device."""

    name = "opencl-igpu-lanes"

    def __init__(self, max_reported: int = 256) -> None:
        try:
            from chronus.execution.opencl_sha256d import OpenCLSha256dMinerBackend
        except Exception as exc:
            raise LaneUnavailable(f"OpenCL adapter cannot be loaded: {exc}") from exc
        backend = OpenCLSha256dMinerBackend(max_reported=max_reported)
        if not backend.is_available():
            raise LaneUnavailable(
                "no OpenCL device (needs pyopencl, an OpenCL runtime and CHRONUS_ENABLE_OPENCL_MINER=1)"
            )
        self._backend = backend
        self.device = dict(backend.get_queue_status().get("device") or {})
        self.lanes = max(1, int(self.device.get("compute_units") or 1))

    def describe(self) -> Dict[str, Any]:
        return {"backend": self.name, "lanes": self.lanes, "device": self.device}

    def search(self, header80: bytes, start: int, stop: int, target: int) -> List[int]:
        return self._backend.search(bytes(header80), start, stop, target)

    def close(self) -> None:
        return None


def qualify(lanes) -> Dict[str, Any]:
    """Known-answer qualification of a lane set against the host reference."""
    checks = []

    def check(name: str, passed: bool) -> None:
        checks.append({"check": name, "passed": bool(passed)})

    check("reference_block0_hash", sha256d(GENESIS_HEADER)[::-1].hex() == GENESIS_HASH)
    check("reference_block1_hash", sha256d(BLOCK1_HEADER)[::-1].hex() == BLOCK1_HASH)
    low, high = GENESIS_NONCE - 4096, GENESIS_NONCE + 4096
    expected = reference_scan(GENESIS_HEADER, low, high, DIFF1_TARGET)
    try:
        got = lanes.search(GENESIS_HEADER, low, high, DIFF1_TARGET)
        check("genesis_nonce_window", GENESIS_NONCE in expected and sorted(got) == expected)
        easy = 1 << 248
        expected_easy = reference_scan(BLOCK1_HEADER, 0, 2048, easy)
        got_easy = lanes.search(BLOCK1_HEADER, 0, 2048, easy)
        check("block1_easy_target_window", len(expected_easy) > 0 and sorted(got_easy) == expected_easy)
        check("unreachable_target_window", list(lanes.search(BLOCK1_HEADER, 0, 4096, 0)) == [])
    except Exception as exc:  # a lane set that raises does not qualify
        check(f"lane_error:{type(exc).__name__}", False)
    return {
        "backend": lanes.name,
        "lanes": lanes.lanes,
        "passed": all(item["passed"] for item in checks),
        "checks": checks,
    }


def calibrate(lanes, min_elapsed_ns: int = 500_000_000, max_window: int = 1 << 28) -> Tuple[int, int]:
    """Measure the lane set's rate on this host: (nonces evaluated, nanoseconds)."""
    window = max(1, lanes.lanes) << 12
    while True:
        started = time.perf_counter_ns()
        lanes.search(BLOCK1_HEADER, 0, window, 0)
        elapsed = time.perf_counter_ns() - started
        if elapsed >= min_elapsed_ns or window >= max_window:
            return window, max(1, elapsed)
        window = min(max_window, window * 4)


def open_lanes(prefer: str = "auto", process_lanes: Optional[int] = None) -> Tuple[Any, List[Dict[str, Any]]]:
    """Open the fastest lane set that qualifies on this host.

    Returns the lane set and every qualification report, including lane sets
    that were unavailable or did not qualify. Each qualified lane set is
    calibrated, and the one with the higher measured rate is kept.
    """
    if prefer not in {"auto", "opencl", "process"}:
        raise ValueError("prefer must be auto, opencl or process")
    reports: List[Dict[str, Any]] = []
    qualified = []
    if prefer in {"auto", "opencl"}:
        try:
            opencl = OpenCLLanes()
        except LaneUnavailable as exc:
            reports.append({"backend": OpenCLLanes.name, "passed": False, "reason": str(exc)})
        else:
            report = qualify(opencl)
            if report["passed"]:
                work, elapsed = calibrate(opencl)
                report["calibration"] = {"work": work, "elapsed_ns": elapsed,
                                         "per_s": rate_per_second(work, elapsed)}
                qualified.append((opencl, report))
            else:
                opencl.close()
            reports.append(report)
    if prefer in {"auto", "process"}:
        count = process_lanes or discover_host().available_cpus
        processes = ProcessLanes(count)
        report = qualify(processes)
        if report["passed"]:
            work, elapsed = calibrate(processes)
            report["calibration"] = {"work": work, "elapsed_ns": elapsed,
                                     "per_s": rate_per_second(work, elapsed)}
            qualified.append((processes, report))
        else:
            processes.close()
        reports.append(report)
    if not qualified:
        raise LaneUnavailable(f"no lane set qualified on this host: {reports}")
    qualified.sort(key=lambda item: item[1]["calibration"]["per_s"], reverse=True)
    chosen = qualified[0][0]
    for lanes, _ in qualified[1:]:
        lanes.close()
    for report in reports:
        report["selected"] = report.get("backend") == chosen.name
    return chosen, reports

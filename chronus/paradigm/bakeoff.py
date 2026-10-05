"""Honest schedule bakeoff — measurement leg of the paradigm triad.

Compares sequential / golden_stride / phi_tier on the *same* SHA256d accept
predicate. Reports wall time and hashes-to-first-hit. Never invents advantage:
if structured order does not win, the report says so.

This is classical measurement only. No quantum, no EH/s, no device cosplay.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import struct
import time
from typing import Any, Callable

from chronus.paradigm.schedules import (
    GOLDEN_STRIDE,
    ScheduleName,
    assert_golden_stride_constant,
    coverage_unique,
    nonce_walk,
)

# Default synthetic header (76 bytes) — not a live chain tip.
_DEFAULT_HEADER = b"\x01" * 76


def _sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def _hash_header_nonce(header76: bytes, nonce: int) -> bytes:
    if len(header76) != 76:
        raise ValueError("header must be 76 bytes (nonce appended as le u32)")
    blob = header76 + struct.pack("<I", nonce & 0xFFFFFFFF)
    return _sha256d(blob)


@dataclass(frozen=True)
class ScheduleResult:
    name: str
    seed: int
    count: int
    hashes: int
    hits: int
    first_hit_nonce: int | None
    first_hit_index: int | None  # probe index of first accept
    wall_ns: int
    unique: bool
    hashes_per_s: float
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BakeoffReport:
    """Full bakeoff verdict — advantage is measured, never assumed."""

    ok: bool
    header_digest: str
    target_hex: str
    results: tuple[ScheduleResult, ...]
    winner_first_hit: str | None
    winner_throughput: str | None
    structured_beats_sequential_first_hit: bool | None
    negative_result: str
    claim_id: str = "c-paradigm-bakeoff"
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["results"] = [r.as_dict() if hasattr(r, "as_dict") else r for r in self.results]
        return d


def _run_one(
    name: ScheduleName,
    header: bytes,
    target_int: int,
    seed: int,
    count: int,
) -> ScheduleResult:
    walk = nonce_walk(name, seed, count, header=header)
    t0 = time.perf_counter_ns()
    hits = 0
    first_nonce: int | None = None
    first_index: int | None = None
    for i, nonce in enumerate(walk):
        digest = _hash_header_nonce(header, nonce)
        value = int.from_bytes(digest, "little")
        if value <= target_int:
            hits += 1
            if first_nonce is None:
                first_nonce = nonce
                first_index = i
    wall = time.perf_counter_ns() - t0
    hps = (count / (wall / 1e9)) if wall > 0 else 0.0
    return ScheduleResult(
        name=name.value,
        seed=seed,
        count=count,
        hashes=count,
        hits=hits,
        first_hit_nonce=first_nonce,
        first_hit_index=first_index,
        wall_ns=int(wall),
        unique=coverage_unique(walk),
        hashes_per_s=float(hps),
        notes="accept = sha256d(header||nonce) little-endian <= target",
    )


def run_bakeoff(
    *,
    header: bytes | None = None,
    # Easy target so every schedule finds hits in a small window (measurement,
    # not mainnet). ~2^-4 fraction → many hits in 4096 probes.
    target_int: int | None = None,
    seed: int = 0xC0FFEE,
    count: int = 2048,
    schedules: tuple[ScheduleName, ...] = (
        ScheduleName.SEQUENTIAL,
        ScheduleName.GOLDEN_STRIDE,
        ScheduleName.PHI_TIER,
    ),
) -> BakeoffReport:
    """Run the three-way (or custom) schedule bakeoff on one header/target."""
    assert_golden_stride_constant()
    hdr = header if header is not None else _DEFAULT_HEADER
    if len(hdr) != 76:
        raise ValueError("header must be 76 bytes")
    # Default: top ~6% of space so first-hit is usually early but not trivial.
    tgt = int(target_int) if target_int is not None else (1 << 252)
    results = tuple(_run_one(s, hdr, tgt, seed, count) for s in schedules)

    # Integrity: every schedule must keep unique coverage in-window.
    if not all(r.unique for r in results):
        return BakeoffReport(
            ok=False,
            header_digest=hashlib.sha256(hdr).hexdigest(),
            target_hex=f"{tgt:064x}",
            results=results,
            winner_first_hit=None,
            winner_throughput=None,
            structured_beats_sequential_first_hit=None,
            negative_result="schedule produced duplicate nonces — bijection/coverage broken",
            metadata={"stride": GOLDEN_STRIDE},
        )

    def _first_idx(r: ScheduleResult) -> float:
        return float(r.first_hit_index) if r.first_hit_index is not None else float("inf")

    by_first = sorted(results, key=_first_idx)
    by_thru = sorted(results, key=lambda r: r.hashes_per_s, reverse=True)
    winner_first = by_first[0].name if by_first[0].first_hit_index is not None else None
    winner_thru = by_thru[0].name if by_thru else None

    seq = next((r for r in results if r.name == ScheduleName.SEQUENTIAL.value), None)
    structured = [r for r in results if r.name != ScheduleName.SEQUENTIAL.value]
    beats: bool | None = None
    negative = ""
    if seq is not None and seq.first_hit_index is not None and structured:
        best_struct = min(structured, key=_first_idx)
        if best_struct.first_hit_index is None:
            beats = False
            negative = (
                "structured schedules found no hit while sequential did — "
                "no first-hit advantage on this sample"
            )
        else:
            beats = best_struct.first_hit_index < seq.first_hit_index
            if not beats:
                negative = (
                    "structured schedules did not beat sequential on first-hit "
                    "index for this header/target/seed; ordering≠advantage"
                )
            else:
                negative = (
                    "structured order beat sequential on this sample only; "
                    "not a general SHA256d advantage claim"
                )
    elif seq is not None and seq.first_hit_index is None:
        negative = "no schedule found a hit — raise target_int or count"
        beats = None
    else:
        negative = "bakeoff complete"

    return BakeoffReport(
        ok=True,
        header_digest=hashlib.sha256(hdr).hexdigest(),
        target_hex=f"{tgt:064x}",
        results=results,
        winner_first_hit=winner_first,
        winner_throughput=winner_thru,
        structured_beats_sequential_first_hit=beats,
        negative_result=negative,
        metadata={
            "stride": GOLDEN_STRIDE,
            "count": count,
            "seed": seed,
            "accept_predicate": "sha256d_le_u256 <= target",
            "advantage_claimed": False,
        },
    )


def bakeoff_self_check(
    hash_fn: Callable[[bytes, int], bytes] | None = None,
) -> dict[str, Any]:
    """Fast deterministic check used by the triad gate."""
    report = run_bakeoff(count=512, seed=1, target_int=(1 << 255))
    return {
        "ok": report.ok and all(r.unique for r in report.results),
        "report": report.as_dict(),
        "claim_id": report.claim_id,
    }

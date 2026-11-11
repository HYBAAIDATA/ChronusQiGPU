# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Jobs, work units, device results and the independent host recheck.

Two independent code paths build every header:

* work units use ``chronus.execution.stratum.build_header_prefix`` (the
  StratumJob path) to make the 76-byte prefix the device hashes;
* the host recheck before submission uses ``chronus.stratum.gatekeeper``
  (``endian_engine`` swap, merkle and 80-byte assembly) and ``hashlib``.

A candidate is submitted only when the recheck rebuilds the header from the
job fields and confirms SHA-256d(header) <= share target.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Optional, Tuple

from chronus.execution.stratum import StratumJob, StratumSession, build_header_prefix
from chronus.stratum.bip310 import format_extranonce2
from chronus.stratum.gatekeeper import (
    LocalPreSubmitGatekeeper,
    compute_share_target_exact,
    decode_nbits_target,
)
from chronus.stratum.sharding import DedupLedger

from hyba_mine.plan import MASK32, NONCE_SPACE, NoncePlan


def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def share_target(difficulty: Fraction) -> int:
    if not isinstance(difficulty, Fraction):
        raise TypeError("share difficulty must be an exact Fraction")
    return compute_share_target_exact(difficulty)


def le_words(value: int) -> Tuple[int, ...]:
    """256-bit integer as eight little-endian 32-bit words (word 7 most significant)."""
    return tuple((value >> (32 * i)) & MASK32 for i in range(8))


@dataclass(frozen=True)
class MiningJob:
    """A pool job as received, bound to the connection that delivered it."""

    job: StratumJob
    pool_id: str
    generation: int
    epoch: int
    extranonce1: bytes
    extranonce2_size: int
    difficulty: Fraction
    received_at: str

    @property
    def job_id(self) -> str:
        return self.job.job_id

    @property
    def key(self) -> tuple:
        return (self.pool_id, self.generation, self.epoch, self.job.job_id)

    @property
    def en2_limit(self) -> int:
        return 1 << (8 * self.extranonce2_size)

    def en2_bytes(self, counter: int) -> bytes:
        return bytes.fromhex(format_extranonce2(counter, self.extranonce2_size))

    def header_prefix(self, en2: bytes) -> bytes:
        session = StratumSession(extranonce1=self.extranonce1, extranonce2_size=self.extranonce2_size)
        return build_header_prefix(self.job, en2, session)

    def gatekeeper_job(self) -> dict:
        # The job id is scoped to pool, connection and extranonce epoch so the
        # duplicate ledger never confuses equal job ids from different sessions.
        return {
            "job_id": f"{self.pool_id}|{self.generation}|{self.epoch}|{self.job.job_id}",
            "prevhash_hex": self.job.prevhash,
            "coinb1_hex": self.job.coinb1,
            "coinb2_hex": self.job.coinb2,
            "merkle_branches": list(self.job.merkle_branch),
            "version_hex": self.job.version,
            "nbits_hex": self.job.nbits,
        }

    def ledger_view(self) -> dict:
        return {
            "pool": self.pool_id,
            "job_id": self.job.job_id,
            "generation": self.generation,
            "epoch": self.epoch,
            "prevhash": self.job.prevhash,
            "version": self.job.version,
            "nbits": self.job.nbits,
            "ntime": self.job.ntime,
            "clean_jobs": self.job.clean_jobs,
            "merkle_branches": len(self.job.merkle_branch),
            "extranonce2_size": self.extranonce2_size,
            "difficulty": str(self.difficulty),
            "received_at": self.received_at,
        }


@dataclass(frozen=True)
class WorkUnit:
    unit_id: str
    job: Optional[MiningJob]
    en2_counter: int
    en2: bytes
    difficulty: Fraction
    target: int
    plan: NoncePlan
    start: int
    count: int
    probe_offset: int

    @property
    def header_prefix(self) -> bytes:
        return self.plan.header_prefix

    def to_wire(self) -> dict:
        """JSON form for a remote iGPU node: no pool identity, no login."""
        return {
            "unit_id": self.unit_id,
            "header_prefix_hex": self.plan.header_prefix.hex(),
            "target_hex": f"{self.target:064x}",
            "plan": self.plan.describe(),
            "lane_table": list(self.plan.lane_table),
            "start": self.start,
            "count": self.count,
            "probe_offset": self.probe_offset,
        }

    def ledger_view(self) -> dict:
        return {
            "unit_id": self.unit_id,
            "job_id": self.job.job_id,
            "en2": self.en2.hex(),
            "start": self.start,
            "count": self.count,
            "difficulty": str(self.difficulty),
            **self.plan.describe(),
        }


def make_unit(job: MiningJob, en2_counter: int, start: int, count: int, difficulty: Fraction, window_bits: int) -> WorkUnit:
    if count <= 0 or start < 0 or start + count > NONCE_SPACE:
        raise ValueError("work unit range must be a non-empty part of [0, 2**32)")
    en2 = job.en2_bytes(en2_counter)
    prefix = job.header_prefix(en2)
    plan = NoncePlan.for_header(prefix, window_bits)
    context = "|".join(str(part) for part in job.key).encode("utf-8")
    tag = hashlib.sha256(context + prefix + start.to_bytes(4, "little") + count.to_bytes(8, "little")).digest()
    return WorkUnit(
        unit_id=tag[:8].hex(),
        job=job,
        en2_counter=en2_counter,
        en2=en2,
        difficulty=difficulty,
        target=share_target(difficulty),
        plan=plan,
        start=start,
        count=count,
        probe_offset=int.from_bytes(tag[8:16], "little") % count,
    )


def make_device_unit(plan: NoncePlan, start: int, count: int, target: int, tag: str) -> WorkUnit:
    """A unit with no pool job, for known-answer tests on a lane."""
    if count <= 0 or start < 0 or start + count > NONCE_SPACE:
        raise ValueError("unit range must be a non-empty part of [0, 2**32)")
    digest = hashlib.sha256(tag.encode("utf-8") + plan.header_prefix + start.to_bytes(4, "little")).digest()
    return WorkUnit(
        unit_id=digest[:8].hex(),
        job=None,
        en2_counter=0,
        en2=b"",
        difficulty=Fraction(0),
        target=target,
        plan=plan,
        start=start,
        count=count,
        probe_offset=int.from_bytes(digest[8:16], "little") % count,
    )


@dataclass(frozen=True)
class Hit:
    offset: int
    nonce: int


@dataclass(frozen=True)
class WindowResult:
    unit_id: str
    executed: int
    device_ns: int
    hits: Tuple[Hit, ...]
    probe_words: Optional[Tuple[int, ...]]
    executed_route: str
    node: str
    hits_truncated: bool = False
    detail: dict = field(default_factory=dict)


def expected_probe_words(unit: WorkUnit) -> Tuple[int, ...]:
    nonce = unit.plan.nonce_at(unit.start + unit.probe_offset)
    digest = sha256d(unit.header_prefix + nonce.to_bytes(4, "little"))
    return le_words(int.from_bytes(digest, "little"))


def check_result_integrity(unit: WorkUnit, result: WindowResult) -> Optional[str]:
    """Return why a device result cannot be trusted, or None when it holds up."""
    if result.unit_id != unit.unit_id:
        return "result belongs to another work unit"
    if result.executed != unit.count:
        return f"device executed {result.executed} of {unit.count} candidates"
    if result.device_ns <= 0:
        return "device reported no execution time"
    if result.probe_words is None:
        return "device returned no probe digest"
    if tuple(result.probe_words) != expected_probe_words(unit):
        return "device probe digest does not match the host SHA-256d"
    for hit in result.hits:
        if not 0 <= hit.offset < unit.count:
            return "device reported a hit outside the unit"
        if hit.nonce != unit.plan.nonce_at(unit.start + hit.offset):
            return "device reported a nonce that is not on the plan"
    return None


@dataclass(frozen=True)
class RecheckOutcome:
    ok: bool
    reason: Optional[str]
    hash_hex: str
    hash_int: int
    target: int
    block_candidate: bool


class HostRecheck:
    """Independent SHA-256d recheck through ``chronus.stratum.gatekeeper``."""

    def __init__(self) -> None:
        self.gatekeeper = LocalPreSubmitGatekeeper()
        self.dedup = DedupLedger(max_entries=200_000)

    def check(self, job: MiningJob, en2: bytes, nonce: int, difficulty: Fraction) -> RecheckOutcome:
        ok, reason, hash_hex, hash_int, target, is_block = self.gatekeeper.verify_candidate(
            job_data=job.gatekeeper_job(),
            extranonce1_hex=job.extranonce1.hex(),
            extranonce2_hex=en2.hex(),
            extranonce2_size=job.extranonce2_size,
            ntime_hex=job.job.ntime,
            nonce_int=nonce,
            version_bits_hex="00000000",
            pool_mask_hex="00000000",
            current_difficulty=difficulty,
            dedup_ledger=self.dedup,
            active_job_ids=None,
        )
        return RecheckOutcome(
            ok=bool(ok),
            reason=reason.value if reason is not None else None,
            hash_hex=hash_hex,
            hash_int=hash_int,
            target=target,
            block_candidate=bool(is_block),
        )


def network_target(job: MiningJob) -> int:
    return decode_nbits_target(job.job.nbits)

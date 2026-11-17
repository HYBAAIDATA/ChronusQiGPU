# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Jobs, work units, device results and the independent host recheck.

Two independent code paths build every header:

* work units use ``chronus.execution.stratum.build_header_prefix`` (the
  StratumJob path) to make the 76-byte prefix the device hashes;
* the host recheck before submission uses ``chronus.stratum.gatekeeper``
  (``endian_engine`` swap, merkle and 80-byte assembly) and ``hashlib``.

A candidate is submitted only when the recheck rebuilds the header from the
job fields and confirms SHA-256d(header) <= share target.

BIP310 version rolling: when the pool grants a version mask, each unit carries
one rolled nVersion. Rolled bits and the job version combine exactly as
``chronus.stratum.bip310.apply_version_rolling`` (and so the gatekeeper)
combine them: ``(job_version & ~mask) | (bits & mask)``. Index 0 always
reproduces the job's own version, so unrolled work is unchanged.
"""

from __future__ import annotations

import dataclasses
import hashlib
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Optional, Tuple

from chronus.execution.stratum import StratumJob, StratumSession, build_header_prefix
from chronus.stratum.bip310 import DEFAULT_CLIENT_MASK_HEX, apply_version_rolling, format_extranonce2
from chronus.stratum.gatekeeper import (
    LocalPreSubmitGatekeeper,
    compute_share_target_exact,
    decode_nbits_target,
)
from chronus.stratum.sharding import DedupLedger

from hyba_mine.plan import MASK32, NONCE_SPACE, NoncePlan

# The version bits HYBA Mine asks the pool to let it roll (BIP310/BIP320 "1fffe000").
CLIENT_VERSION_MASK = int(DEFAULT_CLIENT_MASK_HEX, 16)
# Fewest granted bits worth rolling. Any granted bit adds header variants without
# recomputing the merkle root, so a reduced grant is accepted (chronus defaults to 16).
VERSION_ROLLING_MIN_BITS = 2


def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def share_target(difficulty: Fraction) -> int:
    if not isinstance(difficulty, Fraction):
        raise TypeError("share difficulty must be an exact Fraction")
    return min((1 << 256) - 1, compute_share_target_exact(difficulty))


def pdep(index: int, mask: int) -> int:
    """Spread the low bits of ``index`` over the set bits of ``mask``, low to high."""
    mask &= MASK32
    if not isinstance(index, int) or index < 0 or index >= 1 << mask.bit_count():
        raise ValueError("version index is outside the version space of the mask")
    out, bit = 0, 0
    while mask:
        low = mask & -mask
        if (index >> bit) & 1:
            out |= low
        bit += 1
        mask ^= low
    return out


def version_space(mask: int) -> int:
    """How many distinct header versions a mask allows (1 when nothing is granted)."""
    return 1 << (mask & MASK32).bit_count()


def roll_version(base: int, mask: int, index: int) -> Tuple[int, int]:
    """(nVersion, version bits) of rolled version ``index``; index 0 is ``base`` itself."""
    bits = (base & mask) ^ pdep(index, mask)
    version, _ = apply_version_rolling(base, mask, bits)
    return version & MASK32, bits


def version_fits(base: int, version: int, bits: int, mask: int) -> bool:
    """True when a pool using ``mask`` rebuilds exactly ``version`` from ``bits``."""
    return (bits & ~mask & MASK32) == 0 and ((base & ~mask) | (bits & mask)) & MASK32 == version


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
    # Count of clean_jobs notifies on the session when this job arrived; a
    # later clean_jobs makes this job stale (see PoolSession.stale_reason).
    clean_seq: int = 0

    @property
    def job_id(self) -> str:
        return self.job.job_id

    @property
    def key(self) -> tuple:
        return (self.pool_id, self.generation, self.epoch, self.job.job_id)

    @property
    def schedule_key(self) -> tuple:
        """Identity of the work itself: ``key`` plus clean_seq and a digest of the whole notify.

        A pool may re-send a job_id with a new header (merkle, ntime, clean_jobs); that is different
        work, so it must not reuse the cursor or issued ranges of the earlier notify.
        """
        header = hashlib.sha256(repr(self.job).encode("utf-8")).hexdigest()
        return (*self.key, self.clean_seq, header)

    @property
    def en2_limit(self) -> int:
        return 1 << (8 * self.extranonce2_size)

    @property
    def base_version(self) -> int:
        return int(self.job.version, 16)

    def en2_bytes(self, counter: int) -> bytes:
        return bytes.fromhex(format_extranonce2(counter, self.extranonce2_size))

    def header_prefix(self, en2: bytes, version: Optional[int] = None) -> bytes:
        session = StratumSession(extranonce1=self.extranonce1, extranonce2_size=self.extranonce2_size)
        job = self.job if version is None else dataclasses.replace(self.job, version=f"{version & MASK32:08x}")
        return build_header_prefix(job, en2, session)

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
    # BIP310: which rolled version this unit hashes. ``version`` is the full
    # nVersion in the prefix (None for device/KAT units without a pool job);
    # ``version_bits`` are the masked bits submitted as the 6th param.
    version_index: int = 0
    version_mask: int = 0
    version_bits: int = 0
    version: Optional[int] = None

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
            # Informational only: the header prefix is authoritative.
            "version_hex": f"{int.from_bytes(self.plan.header_prefix[:4], 'little'):08x}",
            "version_bits_hex": f"{self.version_bits:08x}",
            "version_mask_hex": f"{self.version_mask:08x}",
        }

    def ledger_view(self) -> dict:
        return {
            "unit_id": self.unit_id,
            "job_id": self.job.job_id,
            "en2": self.en2.hex(),
            "start": self.start,
            "count": self.count,
            "difficulty": str(self.difficulty),
            "version_index": self.version_index,
            "version": f"{self.version:08x}" if self.version is not None else None,
            "version_bits": f"{self.version_bits:08x}",
            "version_mask": f"{self.version_mask:08x}",
            **self.plan.describe(),
        }


def make_unit(job: MiningJob, en2_counter: int, start: int, count: int, difficulty: Fraction, window_bits: int,
              *, version_mask: int = 0, version_index: int = 0) -> WorkUnit:
    if count <= 0 or start < 0 or start + count > NONCE_SPACE:
        raise ValueError("work unit range must be a non-empty part of [0, 2**32)")
    if (not isinstance(version_mask, int) or isinstance(version_mask, bool) or not 0 <= version_mask <= MASK32
            or version_mask & ~CLIENT_VERSION_MASK):
        raise ValueError("version mask must be a subset of the requested mask 1fffe000")
    version, bits = roll_version(job.base_version, version_mask, version_index)
    en2 = job.en2_bytes(en2_counter)
    # Each rolled version is a distinct 76-byte prefix, so it is part of the unit id below.
    prefix = job.header_prefix(en2, version)
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
        version_index=version_index,
        version_mask=version_mask,
        version_bits=bits,
        version=version,
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


class UnitAborted(RuntimeError):
    """A lane stopped a unit early because ``abort(unit_id)`` asked it to.

    ``executed`` is the lane's own progress counter for the part it ran; it is
    not verified (the probe digest may lie in the part that did not run), so
    it is never counted as work or hashrate.
    """

    def __init__(self, unit_id: str, executed: int, device_ns: int, route: str, node: str, hits_found: int = 0) -> None:
        super().__init__(f"unit {unit_id} stopped after {executed} candidates (aborted)")
        self.unit_id = unit_id
        self.executed = executed
        self.device_ns = device_ns
        self.route = route
        self.node = node
        self.hits_found = hits_found


@dataclass(frozen=True)
class AbortReport:
    """What happened on the device when a stale unit was aborted."""

    OUTCOMES = ("stopped_early", "completed_before_stop", "failed", "still_running", "not_running", "cancelled")

    unit_id: str
    signalled: bool
    outcome: str
    executed: Optional[int]
    device_ns: Optional[int]
    hits_found: Optional[int]
    route: str
    node: str
    waited_ns: int
    detail: dict = field(default_factory=dict)

    def ledger_fields(self) -> dict:
        if self.outcome == "completed_before_stop":
            basis = "whole_unit_verified"
        elif self.executed is not None:
            basis = "route_progress_counter_unverified"
        else:
            basis = None
        return {
            "route": self.route,
            "node": self.node,
            "device_stop": "signalled" if self.signalled else "not_supported",
            "outcome": self.outcome,
            "executed_so_far": self.executed,
            "executed_basis": basis,
            "device_ns": self.device_ns,
            "hits_found_before_stop": self.hits_found,
            "settle_ms": self.waited_ns // 1_000_000,
            **self.detail,
        }


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

    def check(self, job: MiningJob, en2: bytes, nonce: int, difficulty: Fraction, *,
              version_bits: int = 0, version_mask: int = 0) -> RecheckOutcome:
        """Recheck one hit; ``version_bits``/``version_mask`` are the rolled bits and the
        pool's current mask, combined by the gatekeeper exactly as BIP310 (and the pool) do."""
        ok, reason, hash_hex, hash_int, target, is_block = self.gatekeeper.verify_candidate(
            job_data=job.gatekeeper_job(),
            extranonce1_hex=job.extranonce1.hex(),
            extranonce2_hex=en2.hex(),
            extranonce2_size=job.extranonce2_size,
            ntime_hex=job.job.ntime,
            nonce_int=nonce,
            version_bits_hex=f"{version_bits:08x}",
            pool_mask_hex=f"{version_mask:08x}",
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

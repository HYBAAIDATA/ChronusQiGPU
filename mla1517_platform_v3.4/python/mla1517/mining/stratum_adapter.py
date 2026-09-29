"""Exact Stratum V1 job and SHA256d proof adapter for PYTHIA.

The adapter is deliberately narrower than a pool client. It owns the wire
contract needed to turn a live ``mining.notify`` job into a Bitcoin header and
will only return ``mining.submit`` parameters after an independent target
check. Search ordering, TOE context, Cassini metadata, and hardware telemetry
are not proof predicates.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Any, Callable, Mapping, Sequence

WORK_WINDOW_MAX_S = 16 * 60

MAX_UINT256 = (1 << 256) - 1
DIFF1_TARGET = 0x00000000FFFF0000000000000000000000000000000000000000000000000000


class StratumAdapterError(ValueError):
    """Base class for malformed protocol or proof state."""


class StaleJobError(StratumAdapterError):
    """The candidate refers to a job that is no longer current."""


class TargetError(StratumAdapterError):
    """The negotiated target is absent or invalid."""


class CassiniSealError(StratumAdapterError):
    """The configured Cassini seal policy rejected the job/candidate."""


def _hex(value: Any, field: str, *, length: int | None = None) -> str:
    if not isinstance(value, str) or len(value) % 2:
        raise StratumAdapterError(f"{field} must be an even-length hexadecimal string")
    try:
        bytes.fromhex(value)
    except ValueError as exc:
        raise StratumAdapterError(f"{field} is not hexadecimal") from exc
    if length is not None and len(value) != length:
        raise StratumAdapterError(f"{field} must contain exactly {length // 2} bytes")
    return value.lower()


def _uint32_hex(value: Any, field: str) -> str:
    value = _hex(value, field, length=8)
    if int(value, 16) > 0xFFFFFFFF:
        raise StratumAdapterError(f"{field} is not uint32")
    return value


def stratum_prevhash(prevhash_hex: str) -> bytes:
    """Stratum prevhash to the 32 header bytes.

    The pool sends the previous hash as eight 32-bit words, each word
    reversed relative to the header. A full 32-byte reverse is the
    display hash, not the header field.
    """
    raw = bytes.fromhex(prevhash_hex)
    if len(raw) != 32:
        raise StratumAdapterError("prevhash must be 32 bytes")
    return b"".join(raw[index : index + 4][::-1] for index in range(0, 32, 4))


def sha256d(payload: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(payload).digest()).digest()


def _target_from_difficulty(difficulty: Any) -> int:
    """floor(DIFF1_TARGET / difficulty) as an exact rational.

    ``Fraction(str(difficulty))`` is exact for every pool wire form
    (int, float repr, decimal string); non-finite or malformed values
    raise before any arithmetic. No Decimal context precision — the
    quotient carries full 256-bit precision before the floor.
    """
    try:
        value = Fraction(str(difficulty))
    except (ValueError, ZeroDivisionError) as exc:
        raise TargetError("difficulty must be a finite positive number") from exc
    if value <= 0:
        raise TargetError("difficulty must be a finite positive number")
    quotient = Fraction(DIFF1_TARGET, 1) / value
    target = quotient.numerator // quotient.denominator
    if not 0 < target <= MAX_UINT256:
        raise TargetError("difficulty produced an invalid target")
    return target


def _target_from_hex(target_hex: Any) -> int:
    value = _hex(target_hex, "target", length=64)
    target = int(value, 16)
    if not 0 < target <= MAX_UINT256:
        raise TargetError("target must be in the uint256 range and non-zero")
    return target


@dataclass(frozen=True)
class SubscriptionState:
    extranonce1: str
    extranonce2_size: int


@dataclass(frozen=True)
class StratumJob:
    job_id: str
    prevhash: str
    coinb1: str
    coinb2: str
    merkle_branch: tuple[str, ...]
    version: str
    nbits: str
    ntime: str
    clean_jobs: bool
    target: int | None
    cassini_seal: str | None = None


@dataclass(frozen=True)
class ProofCheckedCandidate:
    job_id: str
    extranonce2: str
    ntime: str
    nonce: str
    header: bytes
    digest: bytes
    target: int

    @property
    def submission_params(self) -> list[str]:
        return [self.job_id, self.extranonce2, self.ntime, self.nonce]


CassiniValidator = Callable[[StratumJob, str, str], bool]


class StratumProofAdapter:
    """Stateful, proof-checking adapter for a negotiated Stratum V1 session."""

    def __init__(
        self,
        *,
        require_cassini_seal: bool = False,
        cassini_validator: CassiniValidator | None = None,
    ) -> None:
        self.subscription: SubscriptionState | None = None
        self.target: int | None = None
        self.current_job: StratumJob | None = None
        self.jobs: dict[str, StratumJob] = {}
        self._extranonce2_counter = 0
        self.require_cassini_seal = require_cassini_seal
        self.cassini_validator = cassini_validator

    @staticmethod
    def parse_subscribe_result(result: Any) -> SubscriptionState:
        if not isinstance(result, Sequence) or isinstance(result, (str, bytes)):
            raise StratumAdapterError("mining.subscribe result must be an array")
        if len(result) != 3:
            raise StratumAdapterError("mining.subscribe result must contain exactly three fields")
        _subscriptions, extranonce1, extranonce2_size = result
        extranonce1 = _hex(extranonce1, "extranonce1")
        if not isinstance(extranonce2_size, int) or isinstance(extranonce2_size, bool):
            raise StratumAdapterError("extranonce2_size must be an integer")
        if not 0 <= extranonce2_size <= 32 or extranonce2_size > 16:
            raise StratumAdapterError("extranonce2_size must be between 0 and 16 bytes")
        return SubscriptionState(extranonce1, extranonce2_size)

    @classmethod
    def parse_subscribe_response(cls, message: Mapping[str, Any]) -> SubscriptionState:
        """Validate a raw JSON-RPC ``mining.subscribe`` response."""
        if not isinstance(message, Mapping):
            raise StratumAdapterError("mining.subscribe response must be an object")
        if message.get("error") not in (None, False, []):
            raise StratumAdapterError(f"mining.subscribe returned an error: {message['error']!r}")
        if "result" not in message:
            raise StratumAdapterError("mining.subscribe response has no result")
        return cls.parse_subscribe_result(message["result"])

    @staticmethod
    def parse_notify(params: Any, target: int | None) -> StratumJob:
        if not isinstance(params, Sequence) or isinstance(params, (str, bytes)):
            raise StratumAdapterError("mining.notify params must be an array")
        if len(params) != 9:
            raise StratumAdapterError("mining.notify must contain exactly nine fields")
        (
            job_id,
            prevhash,
            coinb1,
            coinb2,
            merkle_branch,
            version,
            nbits,
            ntime,
            clean_jobs,
        ) = params
        if not isinstance(job_id, str) or not job_id:
            raise StratumAdapterError("job_id must be a non-empty string")
        if not isinstance(merkle_branch, Sequence) or isinstance(merkle_branch, (str, bytes)):
            raise StratumAdapterError("merkle_branch must be an array")
        branches = tuple(_hex(branch, "merkle_branch entry", length=64) for branch in merkle_branch)
        if not isinstance(clean_jobs, bool):
            raise StratumAdapterError("clean_jobs must be boolean")
        return StratumJob(
            job_id=job_id,
            prevhash=_hex(prevhash, "prevhash", length=64),
            coinb1=_hex(coinb1, "coinb1"),
            coinb2=_hex(coinb2, "coinb2"),
            merkle_branch=branches,
            version=_uint32_hex(version, "version"),
            nbits=_uint32_hex(nbits, "nbits"),
            ntime=_uint32_hex(ntime, "ntime"),
            clean_jobs=clean_jobs,
            target=target,
        )

    def handle_subscribe_result(self, result: Any) -> SubscriptionState:
        self.subscription = self.parse_subscribe_result(result)
        self._extranonce2_counter = 0
        return self.subscription

    def handle_message(self, message: Mapping[str, Any]) -> StratumJob | int | None:
        if not isinstance(message, Mapping):
            raise StratumAdapterError("Stratum message must be an object")
        method = message.get("method")
        params = message.get("params")
        if method == "mining.notify":
            job = self.parse_notify(params, self.target)
            if job.clean_jobs:
                self.jobs.clear()
            return self.on_job_received(job)
        if method == "mining.set_difficulty":
            if not isinstance(params, Sequence) or len(params) != 1:
                raise StratumAdapterError("mining.set_difficulty requires one parameter")
            self.target = _target_from_difficulty(params[0])
            self._retarget_jobs()
            return self.target
        if method == "mining.set_target":
            if not isinstance(params, Sequence) or len(params) != 1:
                raise StratumAdapterError("mining.set_target requires one parameter")
            self.target = _target_from_hex(params[0])
            self._retarget_jobs()
            return self.target
        if method == "mining.set_extranonce":
            if self.subscription is None:
                raise StratumAdapterError("mining.set_extranonce before subscribe")
            if (
                not isinstance(params, Sequence)
                or isinstance(params, (str, bytes))
                or len(params) != 2
            ):
                raise StratumAdapterError("mining.set_extranonce requires extranonce1 and size")
            self.subscription = self.parse_subscribe_result([[], params[0], params[1]])
            self._extranonce2_counter = 0
            return self.subscription
        return None

    def on_job_received(
        self, job: StratumJob, *, work_window_seconds: int = WORK_WINDOW_MAX_S
    ) -> StratumJob:
        """Accept a job only with a bounded refresh window."""
        if not 1 <= work_window_seconds <= WORK_WINDOW_MAX_S:
            raise StratumAdapterError(
                f"work window must be between 1 and {WORK_WINDOW_MAX_S} seconds"
            )
        if job.clean_jobs:
            self.jobs.clear()
        self.jobs[job.job_id] = job
        self.current_job = job
        return job

    def _retarget_jobs(self) -> None:
        if self.target is None:
            return
        self.jobs = {job_id: replace(job, target=self.target) for job_id, job in self.jobs.items()}
        if self.current_job is not None:
            self.current_job = replace(self.current_job, target=self.target)

    def drop_session(self) -> None:
        """A dropped socket invalidates the handshake and every job."""
        self.subscription = None
        self.target = None
        self.current_job = None
        self.jobs.clear()
        self._extranonce2_counter = 0

    def next_extranonce2(self) -> str:
        if self.subscription is None:
            raise StratumAdapterError("cannot allocate extranonce2 before subscription")
        width = self.subscription.extranonce2_size * 2
        if width == 0:
            return ""
        limit = 1 << (8 * self.subscription.extranonce2_size)
        if self._extranonce2_counter >= limit:
            raise StratumAdapterError("extranonce2 space exhausted")
        value = f"{self._extranonce2_counter:0{width}x}"
        self._extranonce2_counter += 1
        return value

    def _job_for(self, job_id: str) -> StratumJob:
        if self.current_job is None or job_id not in self.jobs or job_id != self.current_job.job_id:
            raise StaleJobError(f"job {job_id!r} is stale or not current")
        return self.jobs[job_id]

    def build_coinbase(self, extranonce2: str) -> bytes:
        if self.current_job is None:
            raise StaleJobError("cannot build coinbase without a current job")
        return self._coinbase_for(self.current_job, extranonce2)

    def _coinbase_for(self, job: StratumJob, extranonce2: str) -> bytes:
        if self.subscription is None:
            raise StratumAdapterError("cannot build coinbase before subscription")
        expected = self.subscription.extranonce2_size * 2
        extranonce2 = _hex(extranonce2, "extranonce2", length=expected)
        return bytes.fromhex(job.coinb1 + self.subscription.extranonce1 + extranonce2 + job.coinb2)

    def merkle_root(self, job_id: str, extranonce2: str) -> bytes:
        job = self._job_for(job_id)
        root = sha256d(self._coinbase_for(job, extranonce2))
        for branch in job.merkle_branch:
            root = sha256d(root + bytes.fromhex(branch))
        return root

    def build_header(self, job_id: str, extranonce2: str, ntime: str, nonce: int | str) -> bytes:
        job = self._job_for(job_id)
        ntime = _uint32_hex(ntime, "ntime")
        if isinstance(nonce, str):
            nonce_hex = _uint32_hex(nonce, "nonce")
            nonce_value = int(nonce_hex, 16)
        elif isinstance(nonce, int) and not isinstance(nonce, bool) and 0 <= nonce <= 0xFFFFFFFF:
            nonce_value = nonce
        else:
            raise StratumAdapterError("nonce must be a uint32 or eight hex digits")
        header = (
            bytes.fromhex(job.version)[::-1]
            + stratum_prevhash(job.prevhash)
            + self.merkle_root(job_id, extranonce2)
            + bytes.fromhex(ntime)[::-1]
            + bytes.fromhex(job.nbits)[::-1]
            + struct.pack("<I", nonce_value)
        )
        if len(header) != 80:
            raise StratumAdapterError(f"constructed header must be 80 bytes, got {len(header)}")
        return header

    def _check_cassini(self, job: StratumJob, extranonce2: str, nonce: str) -> None:
        if self.require_cassini_seal and not job.cassini_seal:
            raise CassiniSealError("required Cassini seal is absent")
        if self.cassini_validator is not None and not self.cassini_validator(
            job, extranonce2, nonce
        ):
            raise CassiniSealError("Cassini seal validator rejected the candidate")

    def validate_candidate(
        self,
        *,
        job_id: str,
        extranonce2: str,
        ntime: str,
        nonce: int | str,
    ) -> ProofCheckedCandidate:
        job = self._job_for(job_id)
        if job.target is None:
            raise TargetError("no negotiated target is available")
        header = self.build_header(job_id, extranonce2, ntime, nonce)
        nonce_hex = f"{int(nonce, 16):08x}" if isinstance(nonce, str) else f"{nonce:08x}"
        self._check_cassini(job, extranonce2, nonce_hex)
        digest = sha256d(header)
        digest_int = int.from_bytes(digest, "little")
        if digest_int > job.target:
            raise TargetError("candidate SHA256d digest does not meet negotiated target")
        return ProofCheckedCandidate(
            job_id=job_id,
            extranonce2=_hex(
                extranonce2,
                "extranonce2",
                length=(self.subscription.extranonce2_size * 2) if self.subscription else None,
            ),
            ntime=_uint32_hex(ntime, "ntime"),
            nonce=nonce_hex,
            header=header,
            digest=digest,
            target=job.target,
        )

    def submission_params(
        self,
        *,
        worker_name: str,
        job_id: str,
        extranonce2: str,
        ntime: str,
        nonce: int | str,
    ) -> list[str]:
        if not isinstance(worker_name, str) or not worker_name:
            raise StratumAdapterError("worker_name must be non-empty")
        proof = self.validate_candidate(
            job_id=job_id, extranonce2=extranonce2, ntime=ntime, nonce=nonce
        )
        return [worker_name, *proof.submission_params]

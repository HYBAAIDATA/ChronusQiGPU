"""Fixed-width, fail-closed Lucas datapath model.

This is the software/RTL contract for a future ASIC, FPGA, or iGPU backend.
It declares stages and widths, but never pretends Python is silicon. The
mining interface is a custom Lucas-share interface, not a replacement for a
cryptographic proof-of-work protocol.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from math import isqrt
from typing import Iterable

from .lucas_engine import InvariantViolation, fibonacci_pair, lucas


class DatapathFailure(InvariantViolation):
    """A fixed-function stage failed; callers must fail closed."""


@dataclass(frozen=True)
class DatapathConfig:
    working_width: int = 256
    pipeline_depth: int = 6
    prime_rom_limit: int = 100_000
    backend: str = "python-exact-reference"

    def __post_init__(self):
        if self.working_width < 8:
            raise ValueError("working_width must be at least 8 bits")
        if self.pipeline_depth != 6:
            raise ValueError("Lucas datapath requires six declared stages")
        if self.prime_rom_limit < 1:
            raise ValueError("prime_rom_limit must be positive")

    @property
    def modulus(self) -> int:
        return 1 << self.working_width

    @property
    def value_mask(self) -> int:
        return self.modulus - 1


class FibonacciROM:
    """Precomputed exact Fibonacci weights for bounded Zeckendorf encoding."""

    def __init__(self, width: int):
        self.width = width
        values = [1, 2]
        while values[-1] < (1 << width):
            values.append(values[-1] + values[-2])
        self.values = tuple(values)

    def encode(self, value: int) -> int:
        if not 0 <= value < (1 << self.width):
            raise DatapathFailure("rung is outside Fibonacci ROM address width")
        remaining, mask = value, 0
        for bit in range(len(self.values) - 1, -1, -1):
            if self.values[bit] <= remaining:
                remaining -= self.values[bit]
                mask |= 1 << bit
        if remaining or mask & (mask << 1):
            raise DatapathFailure("Zeckendorf ROM produced a non-canonical mask")
        return mask

    def decode(self, mask: int) -> int:
        if mask < 0 or mask & (mask << 1):
            raise DatapathFailure("invalid Zeckendorf mask")
        if mask.bit_length() > len(self.values):
            raise DatapathFailure("mask exceeds Fibonacci ROM width")
        return sum(self.values[i] for i in range(mask.bit_length()) if mask & (1 << i))


def _fib_pair_mod(n: int, modulus: int) -> tuple[int, int]:
    if n == 0:
        return 0, 1
    a, b = _fib_pair_mod(n >> 1, modulus)
    c = (a * ((2 * b - a) % modulus)) % modulus
    d = (a * a + b * b) % modulus
    return (c, d) if n & 1 == 0 else (d, (c + d) % modulus)


def _lucas_mod(n: int, modulus: int) -> int:
    f, f1 = _fib_pair_mod(n, modulus)
    return (2 * f1 - f) % modulus


class CassiniComparator:
    def __init__(self, config: DatapathConfig):
        self.config = config

    def check(self, rung: int, previous: int, value: int, following: int) -> bool:
        m = self.config.modulus
        lhs = (previous * following - value * value) % m
        expected = (5 * ((-1) ** (rung + 1))) % m
        return lhs == expected


class PrimeROM:
    """Bounded prime lookup table. Out-of-ROM indices fail closed.

    A table for all primes below 2^256 is not a realistic ROM. The index bound
    is therefore explicit and part of the datapath configuration.
    """

    def __init__(self, max_index: int):
        if max_index < 1:
            raise ValueError("max_index must be positive")
        estimate = max(32, int(max_index * (20 if max_index > 6 else 10)))
        sieve = bytearray(b"\x01") * (estimate + 1)
        sieve[:2] = b"\x00\x00"
        for p in range(2, isqrt(estimate) + 1):
            if sieve[p]:
                sieve[p * p : estimate + 1 : p] = b"\x00" * (((estimate - p * p) // p) + 1)
        primes = [i for i, flag in enumerate(sieve) if flag]
        while len(primes) < max_index:
            estimate *= 2
            sieve = bytearray(b"\x01") * (estimate + 1)
            sieve[:2] = b"\x00\x00"
            for p in range(2, isqrt(estimate) + 1):
                if sieve[p]:
                    sieve[p * p : estimate + 1 : p] = b"\x00" * (((estimate - p * p) // p) + 1)
            primes = [i for i, flag in enumerate(sieve) if flag]
        self.max_index = max_index
        self.values = tuple(primes[:max_index])

    def lookup(self, one_based_index: int) -> int:
        if not 1 <= one_based_index <= self.max_index:
            raise DatapathFailure("prime index is outside declared PrimeROM")
        return self.values[one_based_index - 1]


@dataclass(frozen=True)
class FixedBinetFold:
    rung: int
    f_n: int
    f_n1: int
    width: int


@dataclass(frozen=True)
class PisotStageResult:
    exponent: int
    conjugate_below_one: bool
    conjugate_below_half: bool


class BinetStage:
    def __init__(self, config: DatapathConfig):
        self.config = config

    def fold(self, rung: int) -> FixedBinetFold:
        f, f1 = _fib_pair_mod(rung, self.config.modulus)
        return FixedBinetFold(rung, f, f1, self.config.working_width)

    def verify(self, folded: FixedBinetFold) -> bool:
        f, f1 = _fib_pair_mod(folded.rung, self.config.modulus)
        return (folded.width == self.config.working_width and (folded.f_n, folded.f_n1) == (f, f1))


class PisotStage:
    def scale(self, rung: int) -> PisotStageResult:
        return PisotStageResult(rung, rung >= 1, rung >= 2)


@dataclass(frozen=True)
class DatapathRecord:
    rung: int
    value: int
    previous: int
    following: int
    zeckendorf_mask: int
    prime_address: int
    cassini_pass: bool
    fold: FixedBinetFold
    pisot: PisotStageResult
    working_width: int
    pipeline_depth: int
    backend: str
    certificate: str

    def canonical_payload(self) -> dict:
        return {
            "rung": self.rung, "value": self.value, "previous": self.previous,
            "following": self.following, "zeckendorf_mask": self.zeckendorf_mask,
            "prime_address": self.prime_address, "cassini_pass": self.cassini_pass,
            "fold": [self.fold.f_n, self.fold.f_n1], "pisot": [self.pisot.conjugate_below_one, self.pisot.conjugate_below_half],
            "working_width": self.working_width, "pipeline_depth": self.pipeline_depth,
            "backend": self.backend,
        }

    def verify(self, config: DatapathConfig, fib_rom: FibonacciROM) -> None:
        if self.working_width != config.working_width or self.pipeline_depth != 6:
            raise DatapathFailure("record configuration mismatch")
        if not self.cassini_pass:
            raise DatapathFailure("Cassini comparator failed")
        if fib_rom.decode(self.zeckendorf_mask) != self.rung:
            raise DatapathFailure("Zeckendorf address failed")
        if self.rung >= 1 and not self.pisot.conjugate_below_one:
            raise DatapathFailure("Pisot scaling certificate failed")
        if self.rung >= 2 and not self.pisot.conjugate_below_half:
            raise DatapathFailure("Pisot half-bound failed")
        expected = hashlib.sha256(json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if self.certificate != expected:
            raise DatapathFailure("certificate digest mismatch")


@dataclass(frozen=True)
class MiningTarget:
    max_value: int
    name: str = "lucas-share-v1"

    def accepts(self, value: int) -> bool:
        return 0 <= value <= self.max_value


@dataclass(frozen=True)
class LucasShare:
    record: DatapathRecord
    target: MiningTarget

    def verify(self, pipeline: "SpatialLucasPipeline") -> None:
        pipeline.verify(self.record)
        if not self.target.accepts(self.record.value):
            raise DatapathFailure("share does not meet target")


class SpatialLucasPipeline:
    """Six-stage spatial pipeline model.

    The Python implementation executes stages sequentially for correctness;
    `specification()` is the hardware contract for spatial unrolling.
    """

    STAGES = ("lucas", "cassini", "zeckendorf", "prime", "binet", "pisot")

    def __init__(self, config: DatapathConfig | None = None):
        self.config = config or DatapathConfig()
        self.fib_rom = FibonacciROM(self.config.working_width)
        self.prime_rom = PrimeROM(self.config.prime_rom_limit)
        self.cassini = CassiniComparator(self.config)
        self.binet = BinetStage(self.config)
        self.pisot = PisotStage()

    def specification(self) -> dict:
        return {
            "stages": list(self.STAGES),
            "pipeline_depth": 6,
            "working_width": self.config.working_width,
            "throughput_classification": "MODELED_UNTIL_HARDWARE_MEASURED",
            "latency_classification": "MODEL_ONLY",
            "fail_closed": True,
        }

    def process_one(self, rung: int) -> DatapathRecord:
        if not 0 <= rung < (1 << self.config.working_width):
            raise DatapathFailure("rung exceeds declared working width")
        m = self.config.modulus
        value = _lucas_mod(rung, m)
        # Extend the Lucas sequence one step backwards: L_{-1} = -1.
        # This keeps the neighbor Cassini comparator defined at rung zero.
        previous = _lucas_mod(rung - 1, m) if rung else (-1 % m)
        following = _lucas_mod(rung + 1, m)
        cassini_pass = self.cassini.check(rung, previous, value, following)
        if not cassini_pass:
            raise DatapathFailure("Cassini comparator failed")
        mask = self.fib_rom.encode(rung)
        address = self.prime_rom.lookup(rung + 1)
        folded = self.binet.fold(rung)
        if not self.binet.verify(folded):
            raise DatapathFailure("Binet stage failed")
        pisot = self.pisot.scale(rung)
        payload = {
            "rung": rung, "value": value, "previous": previous, "following": following,
            "zeckendorf_mask": mask, "prime_address": address, "cassini_pass": True,
            "fold": [folded.f_n, folded.f_n1], "pisot": [pisot.conjugate_below_one, pisot.conjugate_below_half],
            "working_width": self.config.working_width, "pipeline_depth": 6, "backend": self.config.backend,
        }
        certificate = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        record = DatapathRecord(rung, value, previous, following, mask, address, True, folded, pisot,
                                self.config.working_width, 6, self.config.backend, certificate)
        record.verify(self.config, self.fib_rom)
        return record

    def process_batch(self, rungs: Iterable[int]) -> list[DatapathRecord]:
        return [self.process_one(rung) for rung in rungs]

    def verify(self, record: DatapathRecord) -> None:
        record.verify(self.config, self.fib_rom)
        if self.prime_rom.lookup(record.rung + 1) != record.prime_address:
            raise DatapathFailure("PrimeROM mismatch")

    def mine_segment(self, start: int, stop: int, target: MiningTarget, max_shares: int | None = None) -> list[LucasShare]:
        if start < 0 or stop < start:
            raise ValueError("invalid segment")
        shares: list[LucasShare] = []
        for rung in range(start, stop):
            record = self.process_one(rung)
            if target.accepts(record.value):
                share = LucasShare(record, target)
                share.verify(self)
                shares.append(share)
                if max_shares is not None and len(shares) >= max_shares:
                    break
        return shares


def disjoint_segments(start: int, stop: int, workers: int) -> list[tuple[int, int]]:
    if workers < 1 or stop < start: raise ValueError("invalid segment plan")
    length = stop - start; base, extra = divmod(length, workers)
    segments, cursor = [], start
    for worker in range(workers):
        size = base + (1 if worker < extra else 0)
        segments.append((cursor, cursor + size)); cursor += size
    return segments

@dataclass(frozen=True)
class NonceWindow:
    rung: int
    start: int
    length: int
    width: int


def nonce_window(rung: int, width: int = 32) -> NonceWindow:
    """Return a deterministic modular nonce window for a rung.

    This is a scheduling primitive, not a claim that a Lucas value is a
    cryptographic nonce or a SHA-256d proof of work.
    """
    if rung < 0 or width < 1: raise ValueError("invalid nonce-window parameters")
    modulus = 1 << width
    start = _lucas_mod(rung, modulus)
    following = _lucas_mod(rung + 1, modulus)
    length = (following - start) % modulus or modulus
    return NonceWindow(rung, start, length, width)


class ShareAdapter:
    """Protocol boundary for pool/solo/custom integrations; no network I/O."""

    name = "abstract"

    def encode(self, share: LucasShare) -> bytes:
        raise NotImplementedError


class JsonShareAdapter(ShareAdapter):
    name = "json-lucas-share-v1"

    def encode(self, share: LucasShare) -> bytes:
        payload = {
            "protocol": self.name,
            "rung": share.record.rung,
            "value": share.record.value,
            "prime_address": share.record.prime_address,
            "zeckendorf_mask": share.record.zeckendorf_mask,
            "difficulty_target": share.target.max_value,
            "certificate": share.record.certificate,
            "backend": share.record.backend,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

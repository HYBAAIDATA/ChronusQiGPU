"""Golden Quantum profile integrated with the Turing virtual computer.

This module turns the six-phase Golden Quantum architecture into executable,
auditable software while preserving a strict evidence boundary:

* Layer A: exact or directly verified computation.
* Layer B: ordering and optimisation hypotheses requiring benchmarks.
* Layer C: speculative propositions represented as non-executable metadata.

Nothing here creates infinite physical memory, changes physical constants,
removes communication latency, or bypasses a cryptographic predicate.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from decimal import Decimal, getcontext
from enum import Enum
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .capabilities import capability_report
from .turing_core import t_phi_fold, t_phi_unfold

getcontext().prec = 50


class EvidenceLayer(str, Enum):
    VERIFIED = "A_verified_computational_core"
    EXPERIMENTAL = "B_experimental_hypothesis"
    SPECULATIVE = "C_speculative_foundation"


@dataclass(frozen=True)
class GoldenConstants:
    phi: Decimal = (Decimal(1) + Decimal(5).sqrt()) / Decimal(2)
    speed_of_light_m_s: Decimal = Decimal("299792458")
    planck_constant_j_s: Decimal = Decimal("6.62607015e-34")
    gravitational_constant_si: Decimal = Decimal("6.67430e-11")
    fine_structure_constant: Decimal = Decimal("0.0072973525693")
    codata_revision: str = "CODATA-2018"


GOLDEN_CONSTANTS = GoldenConstants()


@dataclass(frozen=True)
class ParameterContext:
    values: Mapping[str, Decimal]
    overrides: Mapping[str, Decimal]
    truth_class: str = "parameterised_simulation_context"
    evidence_layer: EvidenceLayer = EvidenceLayer.VERIFIED
    physical_constants_mutated: bool = False


class UniversalConstantInterface:
    """Immutable reference constants plus explicit simulation overrides."""

    def __init__(self, constants: GoldenConstants = GOLDEN_CONSTANTS):
        self._reference = MappingProxyType(
            {
                "phi": constants.phi,
                "c": constants.speed_of_light_m_s,
                "h": constants.planck_constant_j_s,
                "G": constants.gravitational_constant_si,
                "alpha": constants.fine_structure_constant,
            }
        )

    @property
    def reference(self) -> Mapping[str, Decimal]:
        return self._reference

    def context(self, **overrides: Any) -> ParameterContext:
        unknown = set(overrides) - set(self._reference)
        if unknown:
            raise KeyError(f"unknown simulation constants: {sorted(unknown)}")
        normalized = {name: Decimal(str(value)) for name, value in overrides.items()}
        if any(not value.is_finite() for value in normalized.values()):
            raise ValueError("simulation constants must be finite")
        values = dict(self._reference)
        values.update(normalized)
        return ParameterContext(
            values=MappingProxyType(values),
            overrides=MappingProxyType(normalized),
        )


@dataclass(frozen=True)
class PrimeGapAddress:
    logical_index: int
    left_prime: int
    right_prime: int
    gap: int
    offset: int
    evidence_layer: EvidenceLayer = EvidenceLayer.VERIFIED


class PrimeGapAddressSpace:
    """Finite, deterministic prime-gap addressing over allocated metadata."""

    def __init__(self, prime_count: int = 4096):
        if prime_count < 2:
            raise ValueError("prime_count must be at least two")
        self.primes = tuple(self._first_primes(int(prime_count)))

    @staticmethod
    def _first_primes(count: int) -> list[int]:
        primes: list[int] = []
        candidate = 2
        while len(primes) < count:
            limit = math.isqrt(candidate)
            if all(candidate % prime for prime in primes if prime <= limit):
                primes.append(candidate)
            candidate = 3 if candidate == 2 else candidate + 2
        return primes

    def address(self, logical_index: int) -> PrimeGapAddress:
        if logical_index < 0:
            raise ValueError("logical_index must be non-negative")
        slot = int(logical_index) % (len(self.primes) - 1)
        left, right = self.primes[slot], self.primes[slot + 1]
        gap = right - left
        return PrimeGapAddress(
            logical_index=int(logical_index),
            left_prime=left,
            right_prime=right,
            gap=gap,
            offset=int(logical_index) % gap,
        )

    def report(self) -> dict[str, Any]:
        return {
            "allocated_prime_count": len(self.primes),
            "largest_prime": self.primes[-1],
            "physical_bytes": len(self.primes) * 8,
            "infinite_memory_claim": False,
            "truth_class": "finite_prime_gap_addressing",
            "evidence_layer": EvidenceLayer.VERIFIED.value,
        }


@dataclass(frozen=True)
class GoldenFoldArtifact:
    folded_payload: bytes
    level_lengths: tuple[int, ...]
    original_sha256: str
    depth: int
    evidence_layer: EvidenceLayer = EvidenceLayer.VERIFIED
    truth_class: str = "exact_reversible_transform"


@dataclass(frozen=True)
class SearchAttestation:
    schema: str
    strategy: str
    base: int
    count: int
    stride: int
    complete_permutation: bool
    candidate_digest: str
    evidence_layer: EvidenceLayer
    advantage_claimed: bool
    digest: str


class MandelbrotResonanceEngine:
    """Deterministic Mandelbrot escape-time score used only for ordering."""

    def __init__(self, max_iter: int = 64):
        if max_iter < 1:
            raise ValueError("max_iter must be positive")
        self.max_iter = int(max_iter)

    def score(self, value: int) -> float:
        value = int(value) & 0xFFFFFFFF
        real = -2.0 + 2.47 * (((value >> 16) & 0xFFFF) / 65535.0)
        imag = -1.12 + 2.24 * ((value & 0xFFFF) / 65535.0)
        zr = zi = 0.0
        for iteration in range(self.max_iter):
            zr, zi = zr * zr - zi * zi + real, 2.0 * zr * zi + imag
            if zr * zr + zi * zi > 4.0:
                return iteration / self.max_iter
        return 1.0


class GoldenQuantumCore:
    """Evidence-scoped Golden Quantum surface inside the Turing VQC."""

    def __init__(self, system: Any = None, *, prime_count: int = 4096):
        self.system = system
        self.constants = GOLDEN_CONSTANTS
        self.uci = UniversalConstantInterface(self.constants)
        self.memory = PrimeGapAddressSpace(prime_count)
        self.mandelbrot = MandelbrotResonanceEngine()

    def fold(self, payload: bytes, depth: int = 1) -> GoldenFoldArtifact:
        if depth < 0 or depth > 256:
            raise ValueError("depth must be in [0, 256]")
        raw = bytes(payload)
        digest = hashlib.sha256(raw).hexdigest()
        folded = raw
        lengths: list[int] = []
        for _ in range(int(depth)):
            lengths.append(len(folded))
            folded = t_phi_fold(folded)
        artifact = GoldenFoldArtifact(folded, tuple(lengths), digest, int(depth))
        if self.unfold(artifact) != raw:
            raise RuntimeError("golden fold round trip failed")
        return artifact

    @staticmethod
    def unfold(artifact: GoldenFoldArtifact) -> bytes:
        raw = artifact.folded_payload
        for original_length in reversed(artifact.level_lengths):
            raw = t_phi_unfold(raw, original_length)
        if hashlib.sha256(raw).hexdigest() != artifact.original_sha256:
            raise ValueError("golden fold integrity check failed")
        return raw

    @staticmethod
    def _coprime_stride(count: int) -> int:
        if count == 1:
            return 1
        stride = max(1, int(Decimal(count) / GOLDEN_CONSTANTS.phi))
        while math.gcd(stride, count) != 1:
            stride += 1
        return stride

    def order_search(
        self,
        base: int,
        count: int,
        *,
        mandelbrot_prefix: int = 0,
    ) -> tuple[tuple[int, ...], SearchAttestation]:
        if count < 1 or count > 1_000_000:
            raise ValueError("count must be in [1, 1_000_000]")
        if base < 0 or base + count > 2**32:
            raise ValueError("search interval must remain in uint32")
        stride = self._coprime_stride(int(count))
        offsets = [(index * stride) % count for index in range(count)]
        prefix = min(max(0, int(mandelbrot_prefix)), count)
        if prefix:
            head = sorted(
                offsets[:prefix],
                key=lambda offset: (-self.mandelbrot.score(base + offset), offset),
            )
            offsets = head + offsets[prefix:]
        candidates = tuple(base + offset for offset in offsets)
        complete = len(set(candidates)) == count and set(candidates) == set(
            range(base, base + count)
        )
        candidate_digest = hashlib.sha256(
            b"".join(value.to_bytes(4, "little") for value in candidates)
        ).hexdigest()
        body = {
            "schema": "turing.golden_quantum.search.v1",
            "strategy": "golden_coprime_with_optional_mandelbrot_prefix",
            "base": base,
            "count": count,
            "stride": stride,
            "complete_permutation": complete,
            "candidate_digest": candidate_digest,
            "evidence_layer": EvidenceLayer.EXPERIMENTAL.value,
            "advantage_claimed": False,
        }
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return candidates, SearchAttestation(
            schema=body["schema"],
            strategy=body["strategy"],
            base=body["base"],
            count=body["count"],
            stride=body["stride"],
            complete_permutation=body["complete_permutation"],
            candidate_digest=body["candidate_digest"],
            evidence_layer=EvidenceLayer(body["evidence_layer"]),
            advantage_claimed=body["advantage_claimed"],
            digest=digest,
        )

    @staticmethod
    def verify_attestation(attestation: SearchAttestation) -> bool:
        body = asdict(attestation)
        claimed = body.pop("digest")
        body["evidence_layer"] = attestation.evidence_layer.value
        expected = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return claimed == expected and attestation.complete_permutation

    def compute_fabric_report(self) -> dict[str, Any]:
        report = capability_report()
        return {
            "schema": "turing.golden_quantum.compute_fabric.v1",
            "backend_matrix": report["matrix"],
            "claim_boundary_clean": report["claim_boundary_clean"],
            "routing_policy": "capability-admitted; unavailable backends fail closed",
            "truth_class": "declared_and_probed_capability_surface",
            "evidence_layer": EvidenceLayer.VERIFIED.value,
        }

    def phase_report(self) -> dict[str, Any]:
        return {
            "schema": "turing.golden_quantum.phases.v1",
            "phases": [
                {
                    "phase": 1,
                    "implementation": "Turing exact/symbolic backend registry",
                    "evidence_layer": EvidenceLayer.VERIFIED.value,
                },
                {
                    "phase": 2,
                    "implementation": "golden coprime scheduling",
                    "evidence_layer": EvidenceLayer.EXPERIMENTAL.value,
                },
                {
                    "phase": 3,
                    "implementation": "finite prime-gap addressing and exact T_phi custody",
                    "evidence_layer": EvidenceLayer.VERIFIED.value,
                    "infinite_memory": False,
                },
                {
                    "phase": 4,
                    "implementation": "capability-admitted compute-fabric report",
                    "evidence_layer": EvidenceLayer.VERIFIED.value,
                },
                {
                    "phase": 5,
                    "implementation": "Mandelbrot ordering score",
                    "evidence_layer": EvidenceLayer.EXPERIMENTAL.value,
                },
                {
                    "phase": 6,
                    "implementation": "immutable constants plus simulation overrides",
                    "evidence_layer": EvidenceLayer.VERIFIED.value,
                    "physical_constants_mutated": False,
                },
            ],
            "speculative_non_executable": [
                "infinite physical memory",
                "zero-latency communication",
                "physical-constant mutation",
                "direct manifestation of results",
            ],
            "advantage_claimed": False,
        }


__all__ = [
    "EvidenceLayer",
    "GOLDEN_CONSTANTS",
    "GoldenConstants",
    "GoldenFoldArtifact",
    "GoldenQuantumCore",
    "MandelbrotResonanceEngine",
    "ParameterContext",
    "PrimeGapAddress",
    "PrimeGapAddressSpace",
    "SearchAttestation",
    "UniversalConstantInterface",
]

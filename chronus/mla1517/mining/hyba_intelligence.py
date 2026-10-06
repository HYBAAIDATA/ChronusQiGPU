"""Bounded HYBA intelligence ordering for the canonical mining runtime.

This module composes production-safe mining advisory stages:

* Chronus v3.3 candidate-memory custody;
* mining-local geodesic candidate ordering;
* the classical phi-VQC candidate ranker;
* Chronus wall-clock profiling.

PULVINI/data transformation is deliberately absent from this production mining
pipeline. Data custody and folding remain under their data authority; mining
only consumes candidate-ordering logic owned by the mining package.

Every stage is non-consensus. It may only permute a caller-supplied set of
unique uint32 nonces. The SHA-256d/target check and pool response remain the
exclusive proof authorities.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass
import importlib
import struct
from typing import Any

from .geodesic_nonce_planner import GeodesicNoncePlanner


class CandidateBoundaryError(ValueError):
    """A candidate stage violated the bounded permutation contract."""


@dataclass(frozen=True)
class IntelligenceStage:
    name: str
    state: str
    elapsed_seconds: float
    candidate_count: int
    permutation_preserved: bool
    detail: str = ""


@dataclass(frozen=True)
class CandidateOrderResult:
    candidates: tuple[int, ...]
    stages: tuple[IntelligenceStage, ...]
    consensus_authority: bool = False
    proof_authority: bool = False
    claim_boundary: str = "candidate ordering only"

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidates": list(self.candidates),
            "stages": [asdict(stage) for stage in self.stages],
            "consensus_authority": self.consensus_authority,
            "proof_authority": self.proof_authority,
            "claim_boundary": self.claim_boundary,
        }


def _load_symbol(module_names: tuple[str, ...], symbol: str) -> Any:
    errors: list[str] = []
    for module_name in module_names:
        try:
            return getattr(importlib.import_module(module_name), symbol)
        except Exception as exc:  # optional integration boundary
            errors.append(f"{module_name}: {type(exc).__name__}: {exc}")
    raise ImportError("; ".join(errors))


def _default_geodesic(depth: int) -> GeodesicNoncePlanner:
    return GeodesicNoncePlanner(fold_depth=depth)


def _default_vqc() -> Any:
    ranker = _load_symbol(
        (
            "turing_universal_quantum_computer.phi_vqc",
            "turing_universal_quantum_computer.turing_universal_quantum_computer.phi_vqc",
        ),
        "PhiGroverVQC",
    )
    return ranker()


def _default_profile(fn: Callable[[], Any]) -> tuple[Any, float]:
    profile = _load_symbol(("chronus.runtime",), "profile")
    measured = profile(fn, iterations=1)
    return measured.result, float(measured.wall_seconds)


def _default_memory_custody(values: tuple[int, ...]) -> Any:
    table = _load_symbol(("chronus.v33.memory.table",), "Table")
    domain_bits = max(1, (len(values) - 1).bit_length())
    return table.sparse_from_dict(
        {index: nonce for index, nonce in enumerate(values)},
        domain_bits=domain_bits,
        value_bits=32,
    )


def _header_features(header: bytes | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(header, Mapping):
        return {str(key): value for key, value in header.items() if key != "nonce"}
    raw = bytes(header)
    if len(raw) != 80:
        raise ValueError("binary Bitcoin header must contain exactly 80 bytes")
    version = struct.unpack("<I", raw[0:4])[0]
    ntime = struct.unpack("<I", raw[68:72])[0]
    nbits = struct.unpack("<I", raw[72:76])[0]
    return {
        "version": version,
        "prevhash": raw[4:36].hex(),
        "merkle_root": raw[36:68].hex(),
        "ntime": ntime,
        "nbits": nbits,
    }


def _validate_candidates(values: Iterable[int], maximum: int) -> list[int]:
    candidates = list(values)
    if not candidates:
        raise CandidateBoundaryError("candidate window cannot be empty")
    if len(candidates) > maximum:
        raise CandidateBoundaryError(
            f"candidate window exceeds configured maximum ({len(candidates)} > {maximum})"
        )
    normalized: list[int] = []
    for nonce in candidates:
        if isinstance(nonce, bool) or not isinstance(nonce, int):
            raise CandidateBoundaryError("candidate window must contain integer nonces")
        if not 0 <= nonce <= 0xFFFFFFFF:
            raise CandidateBoundaryError("candidate nonce is outside uint32")
        normalized.append(int(nonce))
    if len(set(normalized)) != len(normalized):
        raise CandidateBoundaryError("candidate window contains duplicates")
    return normalized


def _same_permutation(before: list[int], after: list[int]) -> bool:
    return len(before) == len(after) and set(before) == set(after)


class HYBAIntelligencePipeline:
    """Prepare a mining candidate order while preserving the exact set.

    ``fail_open`` applies only to unavailable or failed advisory stages. A
    stage that returns a different candidate set always raises
    :class:`CandidateBoundaryError`.

    ``fold`` is retained solely as a fail-closed compatibility argument. Any
    non-``None`` value is rejected because PULVINI/data folding is not a mining
    runtime responsibility.
    """

    def __init__(
        self,
        *,
        fold_depth: int = 3,
        max_candidates: int = 250_000,
        enable_geodesic: bool = True,
        enable_vqc: bool = True,
        fail_open: bool = True,
        fold: Callable[..., Any] | None = None,
        memory_custody: Callable[[tuple[int, ...]], Any] | None = None,
        geodesic: Any = None,
        vqc: Any = None,
        profiler: Callable[[Callable[[], Any]], tuple[Any, float]] | None = None,
    ) -> None:
        if fold is not None:
            raise ValueError(
                "PULVINI/data fold injection is forbidden in the production mining pipeline"
            )
        if fold_depth < 0:
            raise ValueError("fold_depth must be non-negative")
        if max_candidates < 1:
            raise ValueError("max_candidates must be positive")
        self.fold_depth = int(fold_depth)
        self.max_candidates = int(max_candidates)
        self.enable_geodesic = bool(enable_geodesic)
        self.enable_vqc = bool(enable_vqc)
        self.fail_open = bool(fail_open)
        self._memory_custody = memory_custody or _default_memory_custody
        self._geodesic = geodesic
        self._vqc = vqc
        self._profiler = profiler or _default_profile

    def _stage_failure(
        self,
        name: str,
        candidates: list[int],
        exc: Exception,
    ) -> IntelligenceStage:
        if not self.fail_open:
            raise exc
        return IntelligenceStage(
            name=name,
            state="DEGRADED_BASELINE",
            elapsed_seconds=0.0,
            candidate_count=len(candidates),
            permutation_preserved=True,
            detail=f"{type(exc).__name__}: {exc}",
        )

    def prepare(
        self,
        header: bytes | Mapping[str, Any],
        candidates: Iterable[int],
        *,
        anchor: int | None = None,
    ) -> CandidateOrderResult:
        current = _validate_candidates(candidates, self.max_candidates)
        features = _header_features(header)
        stages: list[IntelligenceStage] = []

        try:
            table, elapsed = self._profiler(
                lambda: self._memory_custody(tuple(current))
            )
            restored = tuple(table.lookup_int(index) for index in range(len(current)))
            if restored != tuple(current):
                raise CandidateBoundaryError(
                    "Chronus v3.3 memory custody changed candidate order"
                )
            stages.append(
                IntelligenceStage(
                    "chronus_v33_memory",
                    "ACTIVE",
                    elapsed,
                    len(current),
                    True,
                    "32-bit sparse table custody",
                )
            )
        except CandidateBoundaryError:
            raise
        except Exception as exc:
            stages.append(self._stage_failure("chronus_v33_memory", current, exc))

        if self.enable_geodesic:
            try:
                planner = self._geodesic or _default_geodesic(self.fold_depth)
                ordered, elapsed = self._profiler(
                    lambda: planner.order_window(current, anchor=anchor)
                )
                ordered = [int(value) for value in ordered]
                if not _same_permutation(current, ordered):
                    raise CandidateBoundaryError(
                        "geodesic stage changed candidate membership"
                    )
                current = ordered
                stages.append(
                    IntelligenceStage(
                        "geodesic",
                        "ACTIVE",
                        elapsed,
                        len(current),
                        True,
                        "mining-local deterministic proximity ordering",
                    )
                )
            except CandidateBoundaryError:
                raise
            except Exception as exc:
                stages.append(self._stage_failure("geodesic", current, exc))

        if self.enable_vqc:
            try:
                ranker = self._vqc or _default_vqc()
                ranked, elapsed = self._profiler(
                    lambda: ranker.rank_candidates(features, current)
                )
                ranked_values = ranked["candidates"] if isinstance(ranked, Mapping) else ranked
                ordered = [int(value) for value in ranked_values]
                if not _same_permutation(current, ordered):
                    raise CandidateBoundaryError("VQC stage changed candidate membership")
                current = ordered
                stages.append(
                    IntelligenceStage(
                        "phi_vqc",
                        "ACTIVE",
                        elapsed,
                        len(current),
                        True,
                        "classical ranker; exact Clifford skeleton; no proof authority",
                    )
                )
            except CandidateBoundaryError:
                raise
            except Exception as exc:
                stages.append(self._stage_failure("phi_vqc", current, exc))

        return CandidateOrderResult(tuple(current), tuple(stages))


__all__ = [
    "CandidateBoundaryError",
    "CandidateOrderResult",
    "HYBAIntelligencePipeline",
    "IntelligenceStage",
]

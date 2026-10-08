"""Production AETHEL -> Tensor -> Hendrix/Pisot -> iGPU adapter.

This is the production default execution plane. It reuses the existing
FourLayerMiningStack storage/tensor/iGPU components, replaces only the probe
schedule with the exact Lucas/Pisot Hendrix schedule, and leaves SHA-256d and
pool consensus authoritative.

Execution-identity contract (D-007): what runs here is deterministic
structured-classical scheduling (a Hendrix coprime-stride permutation of the
nonce window) followed by exhaustive SHA-256d enumeration on a classical
hasher. No quantum execution occurs in this adapter, and every returned
metadata block and provenance event labels it as such: requested, planned
and executed algorithm identities, the implementing module, the execution
mode, the substrate, the fallback disposition and the independent
double-SHA256 verification are all carried on the receipt.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any

from .four_layer_stack import FourLayerMiningStack
from toe.strict_quantum import certify_work_window, verify_certificate
from toe.system import TOESystem
from turing_universal_quantum_computer.pisot import (
    HendrixStructuredSearch,
    QuantumTensorManifest,
    plan_hilbert_coverage,
    require_lucas_execution_scale,
)

_EXECUTION_MODULE = "mining.four_layer_stack:FourLayerMiningStack.mine"
_EXECUTION_MODE = "structured_classical"
_RECEIPT_VERSION = 1


def _canonical_digest(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class ScaledExecutionResult:
    winner: int | None
    digest: bytes | None
    hashes: int
    metadata: dict[str, Any]


class LucasScaledAethelExecutionAdapter:
    """Executor contract consumed by ``ProductionMiner``."""

    def __init__(self, *, n_qubits: int = 11, workers: int = 1, scale_index: int = 76):
        self.n_qubits = int(n_qubits)
        if self.n_qubits < 1:
            raise ValueError("n_qubits must be >= 1")
        # The qubit width is a free parameter of the exact algebra — the
        # mining lane structure and Hendrix schedule work at any width.
        # Only the strict-quantum certificate and consensus gate are fixed.
        # Hardware gate: physical execution is admitted only on the declared
        # Lucas ladder — a stricter subset of the algebraic scale domain.
        # None resolves to the domain default (76) inside Hendrix; gate the
        # effective index, not the sentinel.
        require_lucas_execution_scale(76 if scale_index is None else int(scale_index))
        self.scheduler = HendrixStructuredSearch(workers=workers, scale_index=scale_index)
        self.tensor = QuantumTensorManifest(
            n_qubits=self.n_qubits,
            scale_index=scale_index,
        )
        self.coverage_memory_bytes = os.getenv("PYTHIA_HILBERT_MEMORY_BYTES")
        self.stack = FourLayerMiningStack(n_qubits=self.n_qubits)
        self.toe = TOESystem()

    def _coverage(self, data_bytes: int) -> dict[str, Any]:
        available = int(self.coverage_memory_bytes) if self.coverage_memory_bytes else None
        plan = plan_hilbert_coverage(
            self.n_qubits,
            available_memory_bytes=available,
            data_bytes=data_bytes,
        )
        if not plan.fits:
            raise MemoryError(
                "full-rank Hilbert tensor plus data reserve does not fit configured memory"
            )
        return {
            "n_qubits": plan.n_qubits,
            "dimension": plan.dimension,
            "state_bytes": plan.state_bytes,
            "data_bytes": plan.data_bytes,
            "total_bytes": plan.total_bytes,
            "available_memory_bytes": plan.available_memory_bytes,
            "full_rank": True,
        }

    def execute(self, header: bytes, target: int, base_nonce: int, count: int):
        if len(header) != 80:
            raise ValueError("executor requires an 80-byte header")
        if count < 1:
            raise ValueError("executor count must be positive")
        target_bytes = target.to_bytes(32, "big")
        strict = certify_work_window(header[:76], base_nonce, count)
        if not verify_certificate(strict):
            raise ValueError("strict quantum work certificate failed")

        schedule = self.scheduler.plan(count)
        # One worker is the normal adapter mode; with multiple workers the
        # merged order remains disjoint and covers the complete nonce space.
        ordered = [
            nonce for worker in range(schedule.workers) for nonce in schedule.worker_nonces(worker)
        ]
        # Execution-identity receipt (D-007): requested/planned/executed are
        # recorded separately and truthfully — the Hendrix permutation plans
        # the probe order, exhaustive SHA-256d enumeration executes it on a
        # classical hasher, and nothing quantum executes.
        receipt = {
            "receipt_version": _RECEIPT_VERSION,
            "requested_algorithm": "lucas_scaled_aethel_execution",
            "planned_algorithm": "hendrix_coprime_stride_permutation",
            "executed_algorithm": "sha256d_window_enumeration",
            "implementation_module": _EXECUTION_MODULE,
            "implementation_digest": _canonical_digest(
                {
                    "module": _EXECUTION_MODULE,
                    "schedule": schedule.manifest(),
                }
            ),
            "execution_mode": _EXECUTION_MODE,
            "schedule_digest": _canonical_digest(schedule.manifest()),
            "fallback_used": False,
            "fallback_reason": None,
        }
        self.toe.record_decision(
            "job_received",
            "geometric",
            "prepare_mining_window",
            {
                "base_nonce": base_nonce,
                "count": count,
                "scale_index": self.scheduler.scale.index,
                "execution_receipt": receipt,
            },
            8,
            verified=True,
        )
        header_store = self.stack.aethel.store("header", header)
        folded, original_len = self.stack.tensor.compress(header)
        fold_ok = self.stack.tensor.decompress(folded, original_len) == header
        coverage = self._coverage(len(header) + len(target_bytes))
        try:
            result = self.stack.chronus.mine(header, target_bytes, ordered, max_hashes=count)
        except Exception as exc:
            self.toe.record_decision(
                "execution_failed",
                "geometric",
                "execution_error",
                {
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                    "execution_receipt": receipt,
                },
                11,
                verified=False,
            )
            raise
        cassini = self.stack.turing.cassini_holds(7)
        evidence = self.stack.aethel.store(
            "evidence:latest",
            f"nonce={result['winning_nonce']} recheck={result['recheck_bit_exact']}".encode(),
        )
        receipt["substrate"] = result["hasher_backend"]
        receipt["independent_sha256d_verification"] = {
            "performed": True,
            "method": "host hashlib double-SHA256 digest + consensus target recheck",
            "winner_bit_exact": bool(result["recheck_bit_exact"]),
        }
        self.toe.record_decision(
            "execution_complete",
            "geometric",
            "sha256d_consensus_check",
            {
                "winner": result["winning_nonce"],
                "hashes": int(result["hashes_computed"]),
                "recheck_bit_exact": bool(result["recheck_bit_exact"]),
                "execution_receipt": receipt,
            },
            11,
            verified=bool(result["recheck_bit_exact"]),
        )
        if (
            not fold_ok
            or not cassini
            # A window with no winner is the ordinary outcome, not a failure:
            # only a claimed winner must survive the bit-exact recheck.
            or (result["winning_nonce"] is not None and not result["recheck_bit_exact"])
            or not self.toe.verify_provenance()
        ):
            raise RuntimeError("TOE/AETHEL/Tensor/Hendrix/iGPU invariant failed")
        return ScaledExecutionResult(
            winner=result["winning_nonce"],
            digest=bytes.fromhex(result["winning_hash"]) if result["winning_hash"] else None,
            hashes=int(result["hashes_computed"]),
            metadata={
                "execution_path": "structured_classical",
                "execution_receipt": receipt,
                "coverage": coverage,
                "tensor_scale": self.tensor.scale_manifest(),
                "schedule": schedule.manifest(),
                "strict_quantum": strict,
                "header_store": header_store,
                "evidence_store": evidence,
                "fold_roundtrip_lossless": fold_ok,
                "cassini_holds": cassini,
                "chronus": result,
                "toe": {
                    "provenance_verified": self.toe.verify_provenance(),
                    "records": len(self.toe.provenance_ledger),
                },
            },
        )

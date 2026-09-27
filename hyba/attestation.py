"""Per-dispatch attestation — the provenance record every op must carry.

An :class:`OpAttestation` binds one executed op to the device that ran it,
the measured capability it exercised, the Lucas configuration that shaped
its chunks, and the truth class the result earned. A dispatch that ran
without a derived Lucas config attests ``truth_class="unconfigured"`` —
never "measured". Attestations feed the telemetry hook and the process
ledger; they are the receipt layer of the composed substrate, parallel to
the nonce-window attestations in ``hyba.hybrid.nonce_scheduler``.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class OpAttestation:
    op: str
    backend: str
    device_name: str
    capability_used: Optional[str]
    lucas_rung: Optional[int]
    chunk_size: Optional[int]
    workgroup_size: Optional[int]
    partition_share: Optional[float]
    measured_ns: int
    clock_source: str
    truth_class: str  # "measured" | "cpu_reference" | "unconfigured"
    issued_ns: int = field(default_factory=time.perf_counter_ns)

    def as_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "op": self.op,
            "backend": self.backend,
            "device_name": self.device_name,
            "measured_ns": self.measured_ns,
            "clock_source": self.clock_source,
            "truth_class": self.truth_class,
            "issued_ns": self.issued_ns,
        }
        if self.capability_used is not None:
            out["capability_used"] = self.capability_used
        if self.lucas_rung is not None:
            out["lucas_rung"] = self.lucas_rung
        if self.chunk_size is not None:
            out["chunk_size"] = self.chunk_size
        if self.workgroup_size is not None:
            out["workgroup_size"] = self.workgroup_size
        if self.partition_share is not None:
            out["partition_share"] = self.partition_share
        return out


class AttestationLog:
    """Process-wide append-only ledger of op attestations."""

    _instance: Optional["AttestationLog"] = None
    _init_lock = threading.Lock()

    def __init__(self) -> None:
        self._records: List[OpAttestation] = []
        self._lock = threading.RLock()

    @classmethod
    def get(cls) -> "AttestationLog":
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = AttestationLog()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._init_lock:
            cls._instance = None

    def record(self, attestation: OpAttestation) -> OpAttestation:
        with self._lock:
            self._records.append(attestation)
        return attestation

    def snapshot(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [r.as_dict() for r in self._records]

    def summary(self) -> Dict[str, Any]:
        with self._lock:
            by_op: Dict[str, int] = {}
            by_truth: Dict[str, int] = {}
            for r in self._records:
                by_op[r.op] = by_op.get(r.op, 0) + 1
                by_truth[r.truth_class] = by_truth.get(r.truth_class, 0) + 1
            return {
                "total": len(self._records),
                "by_op": by_op,
                "by_truth_class": by_truth,
            }


def attest_dispatch(
    *,
    op: str,
    result: Any,
    route: Optional[Any] = None,
    partition_share: Optional[float] = None,
) -> OpAttestation:
    """Build + record an attestation for one executed dispatch.

    ``result`` is an ``OpResult`` (or any object exposing the same fields);
    ``route`` is the ``RouteDecision`` that selected the device — its
    lucas_dispatch supplies rung/chunk/workgroup when present. A dispatch
    without a derived Lucas config attests ``unconfigured``.
    """
    dispatch = getattr(result, "lucas_dispatch", {}) or {}
    on_ladder = bool(dispatch.get("on_ladder"))
    truth = getattr(result, "truth_class", "unconfigured")
    if not on_ladder:
        truth = "unconfigured"
    att = OpAttestation(
        op=op,
        backend=getattr(result, "backend", "unknown"),
        device_name=getattr(result, "device_name", "unknown"),
        capability_used=getattr(result, "capability_used", None),
        lucas_rung=dispatch.get("lucas_rung"),
        chunk_size=dispatch.get("chunk_size"),
        workgroup_size=dispatch.get("workgroup_size"),
        partition_share=partition_share,
        measured_ns=int(getattr(result, "measured_ns", 0)),
        clock_source=getattr(result, "clock_source", "perf_counter"),
        truth_class=truth,
    )
    return AttestationLog.get().record(att)


__all__ = ["AttestationLog", "OpAttestation", "attest_dispatch"]

"""CHRONUS execution-lane consumption for the TURING VQC.

CHRONUS owns heterogeneous execution/acceleration (CPU/iGPU/GPU, Virtual-iGPU
plane).  TURING consumes it as an *execution lane*: when a bound accelerator
exists AND Chronus exposes a contracted kernel for the workload, execution
may be dispatched there and the result classified ``HARDWARE_ACCELERATED``.
Until then — and always on a host with no bound device — the lane reports
GATED/UNAVAILABLE and execution stays on the exact classical path.

Truth rules enforced here:

* Device presence is not device execution: ``device_present`` is recorded as
  evidence of *presence*, never as evidence of dispatch.
* A lane state of GATED means "hardware required, absent on this host";
  UNAVAILABLE means "no contracted kernel exists for this workload even if
  hardware were present" — currently true for VQC gate execution, which is a
  recorded cross-agent dependency on the CHRONUS agent.
* This module never fabricates device identity, driver or timing data; every
  field comes from the live ``aethel.chronus`` context or is ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .taxonomy import EvidenceState

__all__ = [
    "ChronusLaneStatus",
    "chronus_available",
    "probe_chronus_lane",
]


def chronus_available() -> bool:
    try:
        from aethel import chronus as _chronus  # noqa: F401
    except Exception:
        return False
    return True


@dataclass(frozen=True)
class ChronusLaneStatus:
    """Truthful status of the hardware execution lane for one workload."""

    lane_state: str  # GATED / UNAVAILABLE / READY / FAIL
    device_present: bool
    device_identity: str | None
    projection_backend: str | None
    workload: str
    execution_path: str  # where execution actually goes
    cross_agent_dependency: str | None
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def probe_chronus_lane(workload: str = "vqc_gate_execution") -> ChronusLaneStatus:
    """Probe the Chronus execution lane for ``workload`` — read-only.

    Only detection is exercised here; probing does not dispatch anything and
    therefore is not execution evidence.
    """
    if not chronus_available():
        return ChronusLaneStatus(
            lane_state=EvidenceState.UNAVAILABLE.value,
            device_present=False,
            device_identity=None,
            projection_backend=None,
            workload=workload,
            execution_path="turing_classical_exact",
            cross_agent_dependency=None,
            reason="aethel.chronus is not importable on this host",
        )
    try:
        from aethel.chronus import ChronusContext

        ctx = ChronusContext()
    except Exception as exc:
        return ChronusLaneStatus(
            lane_state=EvidenceState.FAIL.value,
            device_present=False,
            device_identity=None,
            projection_backend=None,
            workload=workload,
            execution_path="turing_classical_exact",
            cross_agent_dependency="CHRONUS",
            reason=f"ChronusContext construction failed closed: {exc}",
        )
    try:
        gpu_active = bool(getattr(ctx, "gpu_active", False))
        backend = getattr(ctx, "projection_backend", None)
        punch = getattr(ctx, "punch_host", None)
        identity = None
        if punch is not None:
            identity = str(
                getattr(punch, "device_name", None)
                or getattr(punch, "name", None)
                or getattr(punch, "backend", "unknown")
            )
    finally:
        shutdown = getattr(ctx, "shutdown", None)
        if callable(shutdown):
            try:
                shutdown()
            except Exception:
                pass

    # There is no contracted Chronus kernel for VQC gate execution: Chronus
    # provides punch/projection workloads, not circuit kernels.  A bound
    # device therefore upgrades presence only — the lane is UNAVAILABLE for
    # this workload until the CHRONUS agent publishes a VQC kernel contract.
    if gpu_active:
        return ChronusLaneStatus(
            lane_state=EvidenceState.UNAVAILABLE.value,
            device_present=True,
            device_identity=identity,
            projection_backend=backend,
            workload=workload,
            execution_path="turing_classical_exact",
            cross_agent_dependency="CHRONUS",
            reason="bound accelerator present but no contracted Chronus VQC "
            "kernel exists; presence is not execution — dependency on agent A",
        )
    return ChronusLaneStatus(
        lane_state=EvidenceState.GATED.value,
        device_present=False,
        device_identity=None,
        projection_backend=backend,
        workload=workload,
        execution_path="turing_classical_exact",
        cross_agent_dependency="CHRONUS",
        reason="no bound accelerator on this host; hardware lane gated. "
        "VQC gate kernels are additionally a cross-agent dependency on "
        "CHRONUS (agent A)",
    )

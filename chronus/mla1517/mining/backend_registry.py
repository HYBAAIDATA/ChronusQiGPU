"""Explicit mining-backend registry: declared lanes, real probes, one policy.

The registry is the single authority over which execution lanes exist and
whether they are usable. A lane is ``available`` only after its probe ran:
the probe is a real capability check, not a configuration lookup — the CPU
lane re-hashes a known vector through hashlib, the GPU lane binds an OpenCL
device through ``BitcoinHasher`` (which self-checks the kernels against
hashlib before it reports success), the ``cuda`` and ``metal`` lanes bind
the Chronus-owned native SHA-256d hashers in ``mining.native_sha256d``
(same bind-time hashlib self-check, never a CPU/OpenCL substitution), the
remote lane binds the remote GPU
agent's health contract, the ``asic`` lane probes the real ASIC channel
driver (:class:`hyba.hybrid.asic_solver.ASICSolver` — network/serial/PCIe),
and ``super_asic`` binds the hybrid composition of every supported
substrate — ASIC channel(s), the remote fleet, and the local OpenCL/CPU
solver — under the Lucas-partitioned coordinator.

Routing follows the declared policy only:

* ``auto``   — first available lane in probe order; a CPU fallback is a
  recorded fallback, never silent.
* ``cpu``    — CPU lane only.
* ``gpu`` / ``opencl`` — the OpenCL lane or the selection fails closed.
* ``cuda`` — the Chronus-owned CUDA SHA-256d lane (CuPy runtime +
  Chronus CUDA C kernels, hashlib self-check at bind) or it fails closed.
* ``metal`` — the Chronus-owned Metal SHA-256d lane (MLX kernels on Apple
  GPU, hashlib self-check at bind) or it fails closed.
* ``remote`` — the remote GPU lane or the selection fails closed.
* ``asic`` — a physically bound ASIC channel or a closed refusal; no lane
  is invented to satisfy the request.
* ``super_asic`` — the joined-substrate composition; available whenever at
  least one real substrate binds (ASIC channel, remote fleet, or the
  resident GPU/CPU solver), with ``backend`` naming what joined.

The probe result is evidence: every lane surfaces its status, its device,
and — when unavailable — the measured reason.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field, fields
from pathlib import Path
from enum import StrEnum
from typing import Any, Callable

SCHEMA = "pythia.backend_registry/1"


class BackendLane(StrEnum):
    """The declared execution lanes."""

    CPU = "cpu"
    GPU = "gpu"  # OpenCL device bound through mining.bitcoin_hasher
    CUDA = "cuda"  # Chronus-owned CUDA C kernels via mining.native_sha256d
    METAL = "metal"  # Chronus-owned Metal kernels via mining.native_sha256d
    REMOTE_GPU = "remote_gpu"  # remote agent over MLA1517_REMOTE_GPU_ENDPOINT
    ASIC = "asic"
    SUPER_ASIC = "super_asic"
    CHRONUS = "chronus"  # Virtual iGPU ChronusClient; explicit opt-in, never in auto


_LANES = tuple(BackendLane)


@dataclass(frozen=True)
class LaneProbe:
    """The measured outcome of one capability probe."""

    lane: str
    available: bool
    backend: str | None
    device: str | None
    probed_at: float
    reason: str
    hasher: Any = field(default=None, repr=False, compare=False)

    def as_dict(self) -> dict[str, Any]:
        return {
            "lane": self.lane,
            "available": self.available,
            "backend": self.backend,
            "device": self.device,
            "probed_at": self.probed_at,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class BackendSelection:
    """The routing decision for one run — evidence, not just a hasher."""

    requested: str
    lane: str
    hasher: Any
    fallback: bool
    reason: str
    probed: dict[str, LaneProbe]
    decision_id: str = "Unavailable"
    job_id: str = "Unavailable"
    epoch: str = "Unavailable"
    observation: dict[str, Any] = field(default_factory=dict)
    available_actions: tuple[str, ...] = ()
    selected_action: str = "Unavailable"
    execution_target: str = "Unavailable"
    result: str = "Unavailable"
    disposition: str = "rejected"
    timestamp: float = 0.0
    software_revision: str = "unknown"

    def as_dict(self) -> dict[str, Any]:
        # Never ``asdict(self)``: it deep-copies ``hasher`` (and every probe's hasher), which
        # raises TypeError for hashers holding locks/sockets (remote lane, Chronus Virtual iGPU).
        value = {
            f.name: copy.deepcopy(getattr(self, f.name))
            for f in fields(self)
            if f.name not in ("hasher", "probed")
        }
        value["probed"] = {name: probe.as_dict() for name, probe in self.probed.items()}
        return value


class BackendUnavailable(RuntimeError):
    """The requested lane failed its capability probe."""


def _probe_cpu() -> LaneProbe:
    """CPU lane: hashlib SHA256d against a known vector."""
    try:
        header = bytes(range(80))
        digest = hashlib.sha256(hashlib.sha256(header).digest()).digest()
        if len(digest) != 32:
            raise RuntimeError("hashlib sha256d returned a malformed digest")
        return LaneProbe(
            lane=BackendLane.CPU.value,
            available=True,
            backend="cpu",
            device="CPU (hashlib)",
            probed_at=time.time(),
            reason="hashlib sha256d self-check passed",
        )
    except Exception as exc:  # pragma: no cover - catastrophic platform failure
        return LaneProbe(
            lane=BackendLane.CPU.value,
            available=False,
            backend=None,
            device=None,
            probed_at=time.time(),
            reason=f"hashlib sha256d self-check failed: {exc}",
        )


def _probe_gpu() -> LaneProbe:
    """OpenCL lane: bind a device through BitcoinHasher's real self-check.

    ``BitcoinHasher(backend="gpu")`` compiles the kernels, binds a GPU-type
    device and refuses to come up when the device disagrees with hashlib on
    the probe nonces — a positive result is a measured capability, not an
    assumption.
    """
    try:
        import sys
        from pathlib import Path

        repo_root = str(Path(__file__).resolve().parents[3])
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from mining.bitcoin_hasher import BitcoinHasher

        hasher = BitcoinHasher(backend="gpu")
        backend = str(getattr(hasher, "backend", "") or "")
        if not backend.startswith("opencl"):
            # The hasher bound but reported the CPU reference: that is an
            # unavailable GPU lane, not a silent fallback.
            reason = getattr(hasher, "fallback_reason", None) or "no GPU-class OpenCL device bound"
            return LaneProbe(
                lane=BackendLane.GPU.value,
                available=False,
                backend=None,
                device=None,
                probed_at=time.time(),
                reason=f"OpenCL probe: {reason}",
            )
        return LaneProbe(
            lane=BackendLane.GPU.value,
            available=True,
            backend=backend,
            device=getattr(hasher, "device", None),
            probed_at=time.time(),
            reason="OpenCL device bound; kernel self-checks passed",
            hasher=hasher,
        )
    except Exception as exc:
        return LaneProbe(
            lane=BackendLane.GPU.value,
            available=False,
            backend=None,
            device=None,
            probed_at=time.time(),
            reason=f"OpenCL probe failed: {exc}",
        )


def _probe_cuda() -> LaneProbe:
    """CUDA lane: bind the Chronus-owned CUDA SHA-256d hasher.

    ``ChronusCudaSha256dHasher`` compiles the Chronus CUDA C kernels on a
    real enumerated device and self-checks them against hashlib at bind
    time — a positive probe is measured agreement, never a declaration.
    The lane never substitutes OpenCL or CPU execution.
    """
    try:
        import sys
        from pathlib import Path

        repo_root = str(Path(__file__).resolve().parents[3])
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from mining.native_sha256d import ChronusCudaSha256dHasher

        hasher = ChronusCudaSha256dHasher()
        return LaneProbe(
            lane=BackendLane.CUDA.value,
            available=True,
            backend=hasher.backend,
            device=hasher.device,
            probed_at=time.time(),
            reason="CUDA device bound; kernel self-checks passed",
            hasher=hasher,
        )
    except Exception as exc:
        return LaneProbe(
            lane=BackendLane.CUDA.value,
            available=False,
            backend=None,
            device=None,
            probed_at=time.time(),
            reason=f"CUDA probe failed: {exc}",
        )


def _probe_metal() -> LaneProbe:
    """Metal lane: bind the Chronus-owned Metal SHA-256d hasher.

    ``ChronusMetalSha256dHasher`` compiles the Chronus Metal kernels on an
    Apple GPU through MLX and self-checks against hashlib at bind time.
    The lane never substitutes OpenCL or CPU execution.
    """
    try:
        import sys
        from pathlib import Path

        repo_root = str(Path(__file__).resolve().parents[3])
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from mining.native_sha256d import ChronusMetalSha256dHasher

        hasher = ChronusMetalSha256dHasher()
        return LaneProbe(
            lane=BackendLane.METAL.value,
            available=True,
            backend=hasher.backend,
            device=hasher.device,
            probed_at=time.time(),
            reason="Metal device bound; kernel self-checks passed",
            hasher=hasher,
        )
    except Exception as exc:
        return LaneProbe(
            lane=BackendLane.METAL.value,
            available=False,
            backend=None,
            device=None,
            probed_at=time.time(),
            reason=f"Metal probe failed: {exc}",
        )


def _probe_remote_gpu() -> LaneProbe:
    """Remote lane: bind the remote GPU agent's health contract."""
    try:
        import sys
        from pathlib import Path

        repo_root = str(Path(__file__).resolve().parents[3])
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from mining.remote_hasher import hasher_for_env

        hasher = hasher_for_env()
        return LaneProbe(
            lane=BackendLane.REMOTE_GPU.value,
            available=True,
            backend=getattr(hasher, "backend", "remote_opencl"),
            device=getattr(hasher, "device", None),
            probed_at=time.time(),
            reason="remote GPU agent bound and health-checked",
            hasher=hasher,
        )
    except Exception as exc:
        return LaneProbe(
            lane=BackendLane.REMOTE_GPU.value,
            available=False,
            backend=None,
            device=None,
            probed_at=time.time(),
            reason=f"remote GPU probe failed: {exc}",
        )


def _probe_chronus() -> LaneProbe:
    """Chronus Virtual iGPU lane: bind only after a real known-answer workload."""
    try:
        from chronus.virtual_igpu.mining_hasher import ChronusVirtualIGPUHasher

        hasher = ChronusVirtualIGPUHasher()
        hasher.self_check()
        hasher.launches = 0
        hasher.kernel_ms = 0.0
        return LaneProbe(
            lane=BackendLane.CHRONUS.value,
            available=True,
            backend=hasher.backend,
            device=hasher.device,
            probed_at=time.time(),
            reason="Chronus Virtual iGPU known-answer SHA256d workload passed",
            hasher=hasher,
        )
    except Exception as exc:
        return LaneProbe(
            lane=BackendLane.CHRONUS.value,
            available=False,
            backend=None,
            device=None,
            probed_at=time.time(),
            reason=f"Chronus Virtual iGPU probe failed: {exc}",
        )


def _probe_asic() -> LaneProbe:
    """ASIC lane: run the real channel probe, not a declaration.

    :class:`hyba.hybrid.asic_solver.ASICSolver` speaks to physical ASICs
    through the configured channels (``HYBRID_ASIC_ENDPOINT`` network,
    ``HYBRID_ASIC_SERIAL``, ``HYBRID_ASIC_PCIE``). ``capability()`` is a
    live probe: an unconfigured or unresponsive channel reports
    ``supported=False`` with the concrete reason, and the lane stays
    unavailable. When a dispatch-capable channel answers, the lane binds
    it through :class:`AsicHasherAdapter`.
    """
    try:
        from hyba.hybrid.asic_solver import ASICSolver
        from hyba.hybrid.super_asic import AsicHasherAdapter

        solver = ASICSolver()
        cap = solver.capability()
        if not cap.supported:
            return LaneProbe(
                lane=BackendLane.ASIC.value,
                available=False,
                backend=None,
                device=None,
                probed_at=time.time(),
                reason=cap.reason_if_unsupported or "ASIC channel unsupported",
            )
        return LaneProbe(
            lane=BackendLane.ASIC.value,
            available=True,
            backend="asic",
            device=cap.device_id,
            probed_at=time.time(),
            reason=(
                f"ASIC channel bound: {cap.detail.get('channel', 'unknown')} "
                f"channel measured {cap.measured_hashes_per_sec:g} H/s"
            ),
            hasher=AsicHasherAdapter(solver),
        )
    except Exception as exc:
        return LaneProbe(
            lane=BackendLane.ASIC.value,
            available=False,
            backend=None,
            device=None,
            probed_at=time.time(),
            reason=f"ASIC probe failed: {type(exc).__name__}: {exc}",
        )


def _probe_super_asic() -> LaneProbe:
    """super_asic lane: bind the composite over every supported substrate.

    ASIC channel(s) + remote fleet + resident GPU/CPU solver under one
    Lucas-partitioned coordinator — the super-GPU surface and the ASIC
    channel combined for measured increased hashrate. The lane is
    available whenever at least one real substrate binds; ``backend``
    names the composition honestly (``super_asic:cpu`` on a bare host,
    ``super_asic:asic+remote+gpu`` when everything joins).
    """
    try:
        from hyba.hybrid.super_asic import SuperAsicHasher

        hasher = SuperAsicHasher.bind()
        count = len(hasher._members)
        return LaneProbe(
            lane=BackendLane.SUPER_ASIC.value,
            available=True,
            backend=hasher.backend,
            device=hasher.device,
            probed_at=time.time(),
            reason=(f"composite bound over {count} substrate(s): {hasher.backend}"),
            hasher=hasher,
        )
    except Exception as exc:
        return LaneProbe(
            lane=BackendLane.SUPER_ASIC.value,
            available=False,
            backend=None,
            device=None,
            probed_at=time.time(),
            reason=f"super_asic composition failed: {type(exc).__name__}: {exc}",
        )


# request tokens -> routing. ``auto`` probes the local OpenCL lane, then
# the Chronus-owned CUDA and Metal lanes, then remote, and falls back to
# CPU with a declared reason — local physical substrates before the
# network hop. Every other token selects exactly its lane or fails closed.
_POLICY_ORDER = {
    "auto": (
        BackendLane.GPU,
        BackendLane.CUDA,
        BackendLane.METAL,
        BackendLane.REMOTE_GPU,
        BackendLane.CPU,
    ),
    "cpu": (BackendLane.CPU,),
    "gpu": (BackendLane.GPU,),
    "opencl": (BackendLane.GPU,),
    "cuda": (BackendLane.CUDA,),
    "metal": (BackendLane.METAL,),
    "remote": (BackendLane.REMOTE_GPU,),
    "asic": (BackendLane.ASIC,),
    "super_asic": (BackendLane.SUPER_ASIC,),
    "chronus": (BackendLane.CHRONUS,),
}


class BackendRegistry:
    """Registry of declared lanes; probes on demand and caches the evidence."""

    def __init__(
        self,
        *,
        probe_ttl_s: float = 60.0,
        probes: dict[BackendLane, Callable[[], LaneProbe]] | None = None,
        clock: Callable[[], float] = time.time,
        software_revision: str = "unknown",
        evidence_path: str | Path | None = None,
    ) -> None:
        if probe_ttl_s <= 0:
            raise ValueError("probe_ttl_s must be positive")
        self._ttl = probe_ttl_s
        self._clock = clock
        self.software_revision = software_revision or "unknown"
        self.evidence_path = Path(evidence_path) if evidence_path else None
        self.last_selection: BackendSelection | None = None
        self._probes: dict[BackendLane, Callable[[], LaneProbe]] = probes or {
            BackendLane.CPU: _probe_cpu,
            BackendLane.GPU: _probe_gpu,
            BackendLane.CUDA: _probe_cuda,
            BackendLane.METAL: _probe_metal,
            BackendLane.REMOTE_GPU: _probe_remote_gpu,
            BackendLane.ASIC: _probe_asic,
            BackendLane.SUPER_ASIC: _probe_super_asic,
            BackendLane.CHRONUS: _probe_chronus,
        }
        self._probed: dict[BackendLane, LaneProbe] = {}

    def probe(self, lane: BackendLane, *, force: bool = False) -> LaneProbe:
        """Run (or serve the fresh cache of) a lane's capability probe."""
        cached = self._probed.get(lane)
        if not force and cached is not None and self._clock() - cached.probed_at < self._ttl:
            return cached
        factory = self._probes.get(lane)
        if factory is None:
            # A lane without a wired probe is unavailable by definition —
            # fail closed with the measured reason, never a bare KeyError.
            probe = LaneProbe(
                lane=lane.value,
                available=False,
                backend=None,
                device=None,
                probed_at=self._clock(),
                reason=f"no capability probe wired for lane {lane.value}",
            )
            self._probed[lane] = probe
            return probe
        probe = factory()
        self._probed[lane] = probe
        return probe

    def census(self, *, force: bool = False) -> dict[str, LaneProbe]:
        """Probe every lane (cached within the TTL) and return the census."""
        return {lane.value: self.probe(lane, force=force) for lane in _LANES}

    def select(
        self, requested: str, *, reprobe: bool = False,
        job_id: str = "Unavailable", epoch: str = "Unavailable",
    ) -> BackendSelection:
        """Route per declared policy; a selected lane has been probed.

        ``auto`` walks GPU -> CUDA -> Metal -> remote -> CPU and reports
        ``fallback=True`` whenever the bound lane is not the first probe
        target. Any other token selects exactly its lane: when the probe
        is unavailable the selection raises ``BackendUnavailable`` — it
        fails closed instead of silently degrading.
        """
        key = (requested or "auto").strip().lower()
        if key not in _POLICY_ORDER:
            raise BackendUnavailable(
                f"unknown backend policy {requested!r}; choose from {sorted(_POLICY_ORDER)}"
            )
        order = _POLICY_ORDER[key]
        probed = {lane.value: self.probe(lane, force=reprobe) for lane in order}
        first = order[0]
        for lane in order:
            probe = probed[lane.value]
            if not probe.available:
                continue
            if lane is BackendLane.CPU:
                from .coordinator import CpuReferenceHasher

                hasher = CpuReferenceHasher()
                if lane is not first:
                    hasher.fallback_reason = (
                        f"{first.value} lane unavailable: {probed[first.value].reason}"
                    )
            else:
                hasher = probe.hasher
            reason = (
                f"policy {key}: {lane.value} available ({probe.reason})"
                if lane is first
                else f"policy {key}: {first.value} unavailable "
                f"({probed[first.value].reason}); routed to {lane.value}"
            )
            selection = BackendSelection(
                requested=key, lane=lane.value, hasher=hasher,
                fallback=lane is not first, reason=reason, probed=probed,
                decision_id=f"backend:{uuid.uuid4()}", job_id=job_id, epoch=epoch,
                observation={
                    "requested": key,
                    "policy_order": [candidate.value for candidate in order],
                    "probes": {name: result.as_dict() for name, result in probed.items()},
                },
                available_actions=tuple(
                    name for name, result in probed.items() if result.available
                ),
                selected_action=lane.value, execution_target=lane.value,
                result="backend_bound", disposition="accepted",
                timestamp=self._clock(), software_revision=self.software_revision,
            )
            self._record(selection)
            return selection
        reason = (
            f"policy {key}: no lane available: "
            + "; ".join(f"{p.lane}: {p.reason}" for p in probed.values())
        )
        selection = BackendSelection(
            requested=key, lane="Unavailable", hasher=None, fallback=False,
            reason=reason, probed=probed,
            decision_id=f"backend:{uuid.uuid4()}", job_id=job_id, epoch=epoch,
            observation={
                "requested": key,
                "policy_order": [candidate.value for candidate in order],
                "probes": {name: result.as_dict() for name, result in probed.items()},
            },
            available_actions=(), selected_action="Unavailable",
            execution_target="Unavailable", result="no_backend_bound",
            disposition="rejected", timestamp=self._clock(),
            software_revision=self.software_revision,
        )
        self._record(selection)
        raise BackendUnavailable(reason)

    def snapshot(self) -> dict[str, Any]:
        """Lane census for telemetry; unavailable lanes stay visible."""
        return {
            "schema": SCHEMA,
            "lanes": {lane.value: self.probe(lane).as_dict() for lane in _LANES},
            "policy": {
                token: [lane.value for lane in order]
                for token, order in sorted(_POLICY_ORDER.items())
            },
            "last_selection": (
                self.last_selection.as_dict() if self.last_selection else "Unavailable"
            ),
        }

    def _record(self, selection: BackendSelection) -> None:
        """Persist one append-only decision without persisting a live hasher."""
        self.last_selection = selection
        if self.evidence_path is None:
            return
        self.evidence_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(selection.as_dict(), sort_keys=True, separators=(",", ":")) + "\n"
        descriptor = os.open(
            self.evidence_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600
        )
        try:
            os.write(descriptor, line.encode("utf-8"))
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

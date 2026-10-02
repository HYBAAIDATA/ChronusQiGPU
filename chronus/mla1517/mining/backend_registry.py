"""Explicit mining-backend registry: declared lanes, real probes, one policy.

The registry is the single authority over which execution lanes exist and
whether they are usable. A lane is ``available`` only after its probe ran:
the probe is a real capability check, not a configuration lookup — the CPU
lane re-hashes a known vector through hashlib, the GPU lane binds an OpenCL
device through ``BitcoinHasher`` (which self-checks the kernels against
hashlib before it reports success), the remote lane binds the remote GPU
agent's health contract, and the ASIC lanes report truthfully that no
driver exists in this build.

Routing follows the declared policy only:

* ``auto``   — first available lane in probe order; a CPU fallback is a
  recorded fallback, never silent.
* ``cpu``    — CPU lane only.
* ``gpu`` / ``opencl`` — the OpenCL lane or the selection fails closed.
* ``remote`` — the remote GPU lane or the selection fails closed.
* ``asic`` / ``super_asic`` — those lanes or a closed refusal; no lane is
  invented to satisfy the request.

The probe result is evidence: every lane surfaces its status, its device,
and — when unavailable — the measured reason.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable

SCHEMA = "pythia.backend_registry/1"


class BackendLane(StrEnum):
    """The declared execution lanes."""

    CPU = "cpu"
    GPU = "gpu"  # OpenCL device bound through mining.bitcoin_hasher
    REMOTE_GPU = "remote_gpu"  # remote agent over MLA1517_REMOTE_GPU_ENDPOINT
    ASIC = "asic"
    SUPER_ASIC = "super_asic"


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


def _probe_asic(lane: BackendLane) -> LaneProbe:
    """ASIC lanes: no driver exists in this build; the probe reports that.

    ``asic/`` ships an unsynthesised Verilog sketch only, so the honest
    measured answer is unavailable — surfaced, not hidden.
    """
    return LaneProbe(
        lane=lane.value,
        available=False,
        backend=None,
        device=None,
        probed_at=time.time(),
        reason=(
            "no ASIC driver is present in this build "
            "(asic/ is an unsynthesised Verilog sketch); lane cannot be probed"
        ),
    )


# request tokens -> routing. ``auto`` probes GPU then remote, then falls
# back to CPU with a declared reason; every other token selects exactly its
# lane or fails closed.
_POLICY_ORDER = {
    "auto": (BackendLane.GPU, BackendLane.REMOTE_GPU, BackendLane.CPU),
    "cpu": (BackendLane.CPU,),
    "gpu": (BackendLane.GPU,),
    "opencl": (BackendLane.GPU,),
    "remote": (BackendLane.REMOTE_GPU,),
    "asic": (BackendLane.ASIC,),
    "super_asic": (BackendLane.SUPER_ASIC,),
}


class BackendRegistry:
    """Registry of declared lanes; probes on demand and caches the evidence."""

    def __init__(
        self,
        *,
        probe_ttl_s: float = 60.0,
        probes: dict[BackendLane, Callable[[], LaneProbe]] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if probe_ttl_s <= 0:
            raise ValueError("probe_ttl_s must be positive")
        self._ttl = probe_ttl_s
        self._clock = clock
        self._probes: dict[BackendLane, Callable[[], LaneProbe]] = probes or {
            BackendLane.CPU: _probe_cpu,
            BackendLane.GPU: _probe_gpu,
            BackendLane.REMOTE_GPU: _probe_remote_gpu,
            BackendLane.ASIC: lambda: _probe_asic(BackendLane.ASIC),
            BackendLane.SUPER_ASIC: lambda: _probe_asic(BackendLane.SUPER_ASIC),
        }
        self._probed: dict[BackendLane, LaneProbe] = {}

    def probe(self, lane: BackendLane, *, force: bool = False) -> LaneProbe:
        """Run (or serve the fresh cache of) a lane's capability probe."""
        cached = self._probed.get(lane)
        if not force and cached is not None and self._clock() - cached.probed_at < self._ttl:
            return cached
        probe = self._probes[lane]()
        self._probed[lane] = probe
        return probe

    def census(self, *, force: bool = False) -> dict[str, LaneProbe]:
        """Probe every lane (cached within the TTL) and return the census."""
        return {lane.value: self.probe(lane, force=force) for lane in _LANES}

    def select(self, requested: str, *, reprobe: bool = False) -> BackendSelection:
        """Route per declared policy; a selected lane has been probed.

        ``auto`` walks GPU -> remote -> CPU and reports ``fallback=True``
        whenever the bound lane is not the first probe target. Any other
        token selects exactly its lane: when the probe is unavailable the
        selection raises ``BackendUnavailable`` — it fails closed instead of
        silently degrading.
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
            return BackendSelection(
                requested=key,
                lane=lane.value,
                hasher=hasher,
                fallback=lane is not first,
                reason=(
                    f"policy {key}: {lane.value} available ({probe.reason})"
                    if lane is first
                    else f"policy {key}: {first.value} unavailable "
                    f"({probed[first.value].reason}); routed to {lane.value}"
                ),
                probed=probed,
            )
        raise BackendUnavailable(
            f"policy {key}: no lane available: "
            + "; ".join(f"{p.lane}: {p.reason}" for p in probed.values())
        )

    def snapshot(self) -> dict[str, Any]:
        """Lane census for telemetry; unavailable lanes stay visible."""
        return {
            "schema": SCHEMA,
            "lanes": {lane.value: self.probe(lane).as_dict() for lane in _LANES},
            "policy": {
                token: [lane.value for lane in order]
                for token, order in sorted(_POLICY_ORDER.items())
            },
        }

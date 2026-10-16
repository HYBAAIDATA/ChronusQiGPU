"""Chronus — Apple M5-class multi-pad substrate elevation model.

This module implements the M5 Ultra quantum formulation and its N-pad
elevation protocols — the uniform/asymmetric 10-pad protocol and the
seven-institution consortium variant — as machine-readable,
evidence-labelled substrate facts in Chronus's substrate-agnostic idiom.

Per the repository thesis, the quantum objects here are algebra:
tensor-product registers, GHZ/cluster-state descriptors, Hamiltonian
term registries, and Born-rule observables. They are not claims about
physical entanglement hardware, and nothing in this module is a Chronus
measurement. Every surface carries ``truth_class``/``evidence`` labels
that separate vendor-specification references, documented protocol
numbers, and theoretical projections, and ``measured_by_chronus`` is
False throughout.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Reference constants (labelled vendor/protocol numbers, not measurements)
# ---------------------------------------------------------------------------

M5_ULTRA_DIES = 4
M5MAX_SUBUNITS_PER_DIE = 2
PER_PAD_LOG2_HILBERT_DIM = 64

ULTRAFUSION_LINK_BPS = 4.4e12
ULTRAFUSION_GEN3_DENSITY = 6.0
TB5_BPS = 15.0e9          # 120 Gbit/s expressed in bytes/s
RDMA_TB6_PER_UNIT_BPS = 15.0e9  # 120 Gbit/s per clustered unit, bytes/s
OPTICAL_INTERPAD_BPS = 1.2e15   # Caltech/Cambridge photonic mesh aggregate
CERN_WLCG_TRIGGER_BPS = 1.0e16  # 10 PB/s trigger backplane
HBM4_PAD_BYTES = 2.0e12
HBM4_PAD_BPS = 8.0e12

M5_AI_SPEEDUP = 4.5
M5_RENDER_FACTOR = 1.40
M5_ML_CAPACITY_FACTOR = 2.0

TRUTH_FORMULATION = "quantum_substrate_formulation"
TRUTH_SPEC = "vendor_spec_reference"
TRUTH_PROJECTION = "theoretical_projection"

#: Labelled inter-pad link kinds. Bandwidth is the per-link default; kinds
#: with ``None`` describe channel physics whose rate the protocol carries
#: only as an aggregate (or leaves coherent/unallocated).
LINK_BANDWIDTHS_BPS: Dict[str, Optional[float]] = {
    "ultrafusion": ULTRAFUSION_LINK_BPS,
    "fiber": None,
    "free_space_optical": None,
    "superconducting": None,
    "rdma_tb6": RDMA_TB6_PER_UNIT_BPS,
    "entanglement": None,
}

#: Canonical nearest-neighbour lattice for the documented 10-pad drawing
#: (rows 3-4-3). 15 edges: 7 horizontal + 4 top/middle + 4 middle/bottom.
MESH10_EDGES: Tuple[Tuple[int, int], ...] = (
    (0, 1), (1, 2), (3, 4), (4, 5), (5, 6), (7, 8), (8, 9),
    (0, 3), (1, 4), (2, 5), (2, 6),
    (3, 7), (4, 8), (5, 9), (6, 9),
)


class PadElevationError(ValueError):
    """A pad topology, scheme or elevation parameter was violated."""


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PadSpec:
    """Per-pad resource envelope (classical values, evidence-labelled)."""

    cpu_super_cores: int = 0
    cpu_performance_cores: int = 0
    cpu_efficiency_cores: int = 0
    gpu_cores: int = 0
    gpu_photonic_cores: int = 0
    neural_engine_cores: int = 0
    memory_bytes: float = 0.0
    memory_bandwidth_bytes_per_second: float = 0.0
    log2_hilbert_dim: int = PER_PAD_LOG2_HILBERT_DIM
    evidence: Tuple[str, ...] = ()

    @property
    def cpu_cores(self) -> int:
        return (
            self.cpu_super_cores
            + self.cpu_performance_cores
            + self.cpu_efficiency_cores
        )


@dataclass(frozen=True)
class Pad:
    """One substrate pad: an index, a label, an optional institution, a spec."""

    index: int
    label: str
    spec: PadSpec
    institution: str = ""
    role: str = "compute"
    subunits: int = 1
    notes: Tuple[str, ...] = ()


@dataclass(frozen=True)
class PadLink:
    """A labelled interconnect edge between two pads.

    ``bandwidth_bytes_per_second`` is ``None`` for coherent or aggregate-
    accounted channels — a missing rate is reported, never inferred.
    """

    source: int
    target: int
    kind: str = "ultrafusion"
    bandwidth_bytes_per_second: Optional[float] = None
    evidence: str = TRUTH_FORMULATION


@dataclass(frozen=True)
class FabricChannel:
    """An aggregate fabric-level channel (not a per-edge link)."""

    name: str
    bandwidth_bytes_per_second: Optional[float]
    coherent: bool = False
    evidence: str = TRUTH_PROJECTION


@dataclass(frozen=True)
class MemoryTier:
    """One declared memory tier. ``capacity_bytes`` is None for quantum RAM.

    ``includes_pad_memory`` marks tiers that *describe* the same bytes the
    pads already carry in ``PadSpec.memory_bytes`` (e.g. the on-pad HBM4
    tier), so the fabric does not double-count them in
    ``total_addressable_memory_bytes``.
    """

    name: str
    scope: str
    capacity_bytes: Optional[float]
    bandwidth_bytes_per_second: Optional[float]
    units: int = 1
    coherent: bool = False
    includes_pad_memory: bool = False
    evidence: str = TRUTH_PROJECTION

    @property
    def total_capacity_bytes(self) -> Optional[float]:
        if self.capacity_bytes is None:
            return None
        return self.capacity_bytes * self.units


@dataclass(frozen=True)
class HamiltonianTerm:
    """One symbolic term of the fabric Hamiltonian registry."""

    name: str
    expression: str
    scope: str
    evidence: str = TRUTH_FORMULATION


@dataclass(frozen=True)
class ElevationStrategy:
    rank: int
    strategy: str
    gain: str
    complexity: str
    lead: str = ""


@dataclass(frozen=True)
class InstitutionalAxis:
    institution: str
    axis: str
    contribution: str


# ---------------------------------------------------------------------------
# Topology
# ---------------------------------------------------------------------------

TOPOLOGIES = ("chain", "ring", "mesh", "full_mesh")


def pad_edges(n_pads: int, topology: str = "full_mesh") -> Tuple[Tuple[int, int], ...]:
    """Ordered (i, j) pad pairs for the named interconnect topology.

    ``mesh`` is the documented 3-4-3 nearest-neighbour lattice and is
    defined for the canonical 10-pad layout; other pad counts raise.
    """
    n = int(n_pads)
    if n < 1:
        raise PadElevationError("n_pads must be >= 1")
    topo = str(topology).strip().lower()
    if topo == "chain":
        return tuple((i, i + 1) for i in range(n - 1))
    if topo == "ring":
        edges = [(i, i + 1) for i in range(n - 1)]
        if n > 2:
            edges.append((n - 1, 0))
        return tuple(edges)
    if topo == "full_mesh":
        return tuple((i, j) for i in range(n) for j in range(i + 1, n))
    if topo == "mesh":
        if n != 10:
            raise PadElevationError(
                "mesh topology is defined for the canonical 10-pad "
                "3-4-3 lattice; use chain/ring/full_mesh or supply "
                "explicit links for other pad counts"
            )
        return MESH10_EDGES
    raise PadElevationError(f"unknown topology {topology!r}; known: {TOPOLOGIES}")


def _make_links(
    edges: Sequence[Tuple[int, int]],
    kind: str,
    bandwidth_bps: Optional[float],
    evidence: str,
) -> Tuple[PadLink, ...]:
    return tuple(
        PadLink(
            source=int(i),
            target=int(j),
            kind=kind,
            bandwidth_bytes_per_second=bandwidth_bps,
            evidence=evidence,
        )
        for i, j in edges
    )


# ---------------------------------------------------------------------------
# Fabric
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PadFabric:
    """A substrate-agnostic multi-pad system with a quantum formulation.

    Aggregates are arithmetic over the declared pad/link/channel facts;
    the quantum block is the algebraic formulation (tensor-product
    registers, GHZ/cluster descriptors, unified-projection condition).
    """

    name: str
    pads: Tuple[Pad, ...]
    links: Tuple[PadLink, ...]
    memory_tiers: Tuple[MemoryTier, ...] = ()
    channels: Tuple[FabricChannel, ...] = ()
    topology: str = "full_mesh"
    truth_class: str = TRUTH_FORMULATION
    measured_by_chronus: bool = False
    evidence: Tuple[str, ...] = ()
    notes: Tuple[str, ...] = ()
    # Elevation bookkeeping (None when this fabric IS the baseline).
    reference_pads: Optional[int] = None
    reference_edges: Optional[int] = None
    reference_log2_dim: Optional[int] = None

    # -- counts ---------------------------------------------------------
    @property
    def n_pads(self) -> int:
        return len(self.pads)

    @property
    def n_links(self) -> int:
        return len(self.links)

    @property
    def n_registers(self) -> int:
        return sum(p.subunits for p in self.pads)

    @property
    def hilbert_log2_dim(self) -> int:
        """log2 of the composite register dimension, sum over subunits."""
        return sum(p.subunits * p.spec.log2_hilbert_dim for p in self.pads)

    # -- classical aggregates -------------------------------------------
    def _total(self, attr: str) -> int:
        return int(sum(getattr(p.spec, attr) for p in self.pads))

    @property
    def cpu_super_cores(self) -> int:
        return self._total("cpu_super_cores")

    @property
    def cpu_performance_cores(self) -> int:
        return self._total("cpu_performance_cores")

    @property
    def cpu_efficiency_cores(self) -> int:
        return self._total("cpu_efficiency_cores")

    @property
    def cpu_cores(self) -> int:
        return sum(p.spec.cpu_cores for p in self.pads)

    @property
    def gpu_cores(self) -> int:
        return self._total("gpu_cores")

    @property
    def gpu_photonic_cores(self) -> int:
        return self._total("gpu_photonic_cores")

    @property
    def neural_engine_cores(self) -> int:
        return self._total("neural_engine_cores")

    @property
    def memory_bytes(self) -> float:
        """On-pad memory summed over pads (tiers are reported separately)."""
        return float(sum(p.spec.memory_bytes for p in self.pads))

    @property
    def memory_bandwidth_bps(self) -> float:
        return float(
            sum(p.spec.memory_bandwidth_bytes_per_second for p in self.pads)
        )

    @property
    def total_addressable_memory_bytes(self) -> Optional[float]:
        """On-pad memory plus declared tier capacities.

        Returns ``None`` only if no classical capacity exists at all;
        coherent (quantum RAM) tiers contribute no classical bytes.
        """
        total = self.memory_bytes
        tier_sum = 0.0
        any_tier = False
        for tier in self.memory_tiers:
            if tier.includes_pad_memory:
                continue
            cap = tier.total_capacity_bytes
            if cap is not None:
                tier_sum += cap
                any_tier = True
        total += tier_sum
        if total == 0.0 and not any_tier:
            return None
        return total

    @property
    def ai_speedup_peak(self) -> Optional[float]:
        """Peak AI multiplier: M5_AI_SPEEDUP scaled by NE core ratio to 32."""
        if self.neural_engine_cores <= 0:
            return None
        return M5_AI_SPEEDUP * (self.neural_engine_cores / 32.0)

    # -- interconnect ----------------------------------------------------
    @property
    def interconnect_bandwidth_bps(self) -> float:
        """Sum of per-link rates plus aggregate channel rates.

        Coherent/unallocated channels contribute zero — they are listed,
        not folded into a number.
        """
        link_total = sum(
            link.bandwidth_bytes_per_second or 0.0 for link in self.links
        )
        channel_total = sum(
            ch.bandwidth_bytes_per_second or 0.0 for ch in self.channels
        )
        return float(link_total + channel_total)

    @property
    def links_by_kind(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for link in self.links:
            out[link.kind] = out.get(link.kind, 0) + 1
        return out

    @property
    def coherent_channels(self) -> int:
        return sum(1 for ch in self.channels if ch.coherent)

    # -- quantum formulation ---------------------------------------------
    @property
    def ghz_state(self) -> str:
        n = self.n_pads
        return f"|GHZ_{n}> = (|0>^x{n} + |1>^x{n})/sqrt(2)"

    @property
    def cluster_state(self) -> str:
        return (
            f"|C_{self.n_pads}> = prod_{{(i,j) in E}} CZ_ij |+>^x{self.n_pads}"
        )

    @property
    def unified_projection(self) -> str:
        return "[P_unified, H_fabric] = 0"

    @property
    def state_expression(self) -> str:
        return f"|Psi> = tensor_{{i=1}}^{{{self.n_pads}}} |pad_i>"

    @property
    def hilbert_log2_gain_vs_reference(self) -> Optional[int]:
        if self.reference_log2_dim is None:
            return None
        return self.hilbert_log2_dim - self.reference_log2_dim

    @property
    def topology_gain_vs_reference(self) -> Optional[float]:
        if not self.reference_edges:
            return None
        return self.n_links / float(self.reference_edges)

    def amdahl_bound(self, serial_fraction: float) -> float:
        """S = 1 / (f_serial + f_parallel / n_pads)."""
        f = float(serial_fraction)
        if not (0.0 <= f <= 1.0):
            raise PadElevationError("serial_fraction must be in [0, 1]")
        return 1.0 / (f + (1.0 - f) / max(1, self.n_pads))

    # -- registry ---------------------------------------------------------
    def hamiltonian_terms(self) -> Tuple[HamiltonianTerm, ...]:
        terms: list[HamiltonianTerm] = [
            HamiltonianTerm(
                f"H_pad_{p.index}_{p.institution or 'generic'}",
                "H_CPU + H_GPU + H_NE + H_mem",
                f"pad:{p.label}",
            )
            for p in self.pads
        ]
        for kind in sorted(self.links_by_kind):
            count = self.links_by_kind[kind]
            terms.append(
                HamiltonianTerm(
                    f"H_link_{kind}",
                    f"sum over {count} {kind} edges of J_ij (a_i+ a_j + h.c.)",
                    f"interconnect:{kind} x{count}",
                )
            )
        for ch in self.channels:
            terms.append(
                HamiltonianTerm(
                    f"H_channel_{ch.name}",
                    "coherent channel" if ch.coherent else "aggregate channel",
                    "fabric",
                )
            )
        return tuple(terms)

    def quantum_block(self) -> Dict[str, Any]:
        return {
            "state_expression": self.state_expression,
            "n_pads": self.n_pads,
            "n_registers": self.n_registers,
            "hilbert_log2_dim": self.hilbert_log2_dim,
            "ghz_state": self.ghz_state,
            "cluster_state": self.cluster_state,
            "cluster_state_edges": self.n_links,
            "unified_projection": self.unified_projection,
            "born_rule": "P(k) = |alpha_k|^2",
        }

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "truth_class": self.truth_class,
            "measured_by_chronus": self.measured_by_chronus,
            "topology": self.topology,
            "n_pads": self.n_pads,
            "n_links": self.n_links,
            "links_by_kind": dict(self.links_by_kind),
            "totals": {
                "cpu_super_cores": self.cpu_super_cores,
                "cpu_performance_cores": self.cpu_performance_cores,
                "cpu_efficiency_cores": self.cpu_efficiency_cores,
                "cpu_cores": self.cpu_cores,
                "gpu_cores": self.gpu_cores,
                "gpu_photonic_cores": self.gpu_photonic_cores,
                "neural_engine_cores": self.neural_engine_cores,
                "memory_bytes": self.memory_bytes,
                "memory_bandwidth_bytes_per_second": self.memory_bandwidth_bps,
                "total_addressable_memory_bytes": self.total_addressable_memory_bytes,
                "ai_speedup_peak": self.ai_speedup_peak,
            },
            "interconnect": {
                "aggregate_bandwidth_bytes_per_second": self.interconnect_bandwidth_bps,
                "channels": [
                    {
                        "name": ch.name,
                        "bandwidth_bytes_per_second": ch.bandwidth_bytes_per_second,
                        "coherent": ch.coherent,
                        "evidence": ch.evidence,
                    }
                    for ch in self.channels
                ],
                "coherent_channels": self.coherent_channels,
            },
            "memory_tiers": [
                {
                    "name": t.name,
                    "scope": t.scope,
                    "capacity_bytes": t.capacity_bytes,
                    "units": t.units,
                    "total_capacity_bytes": t.total_capacity_bytes,
                    "bandwidth_bytes_per_second": t.bandwidth_bytes_per_second,
                    "coherent": t.coherent,
                    "includes_pad_memory": t.includes_pad_memory,
                    "evidence": t.evidence,
                }
                for t in self.memory_tiers
            ],
            "quantum": self.quantum_block(),
            "elevation_vs_reference": {
                "reference_pads": self.reference_pads,
                "reference_edges": self.reference_edges,
                "reference_log2_dim": self.reference_log2_dim,
                "hilbert_log2_gain": self.hilbert_log2_gain_vs_reference,
                "topology_gain": self.topology_gain_vs_reference,
            },
            "amdahl": {
                "parallel_units": self.n_pads,
                "ideal_speedup": float(self.n_pads),
                "bound": "S = 1/(f_serial + f_parallel/n_pads)",
            },
            "pads": [
                {
                    "index": p.index,
                    "label": p.label,
                    "institution": p.institution,
                    "role": p.role,
                    "subunits": p.subunits,
                    "spec": asdict(p.spec),
                    "notes": list(p.notes),
                }
                for p in self.pads
            ],
            "links": [
                {
                    "source": link.source,
                    "target": link.target,
                    "kind": link.kind,
                    "bandwidth_bytes_per_second": link.bandwidth_bytes_per_second,
                    "evidence": link.evidence,
                }
                for link in self.links
            ],
            "hamiltonian_terms": [asdict(t) for t in self.hamiltonian_terms()],
            "unified_condition": self.unified_projection,
            "institutions": sorted({p.institution for p in self.pads if p.institution}),
            "evidence": list(self.evidence),
            "notes": list(self.notes),
            "fingerprint": self.fingerprint,
        }

    @property
    def fingerprint(self) -> str:
        payload = {
            "name": self.name,
            "pads": [
                (p.index, p.label, p.institution, p.role, p.subunits, asdict(p.spec))
                for p in self.pads
            ],
            "links": [
                (l.source, l.target, l.kind, l.bandwidth_bytes_per_second)
                for l in self.links
            ],
            "channels": [
                (c.name, c.bandwidth_bytes_per_second, c.coherent)
                for c in self.channels
            ],
            "tiers": [
                (t.name, t.capacity_bytes, t.units, t.coherent, t.includes_pad_memory)
                for t in self.memory_tiers
            ],
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(blob).hexdigest()


# ---------------------------------------------------------------------------
# Canonical fabrics
# ---------------------------------------------------------------------------

_M5_EVIDENCE = (
    "Apple M5 Ultra reference specs via the formulation notes; "
    "GPU core count is an assumption, not a confirmed vendor figure",
)


def _m5_die(index: int) -> Pad:
    return Pad(
        index=index,
        label=f"die{index + 1}",
        institution="apple",
        role="compute",
        subunits=M5MAX_SUBUNITS_PER_DIE,
        spec=PadSpec(
            cpu_super_cores=3,
            cpu_performance_cores=6,
            cpu_efficiency_cores=0,
            gpu_cores=20,
            neural_engine_cores=8,
            memory_bytes=128.0e9,
            memory_bandwidth_bytes_per_second=0.3e12,
            evidence=("assumed_gpu_core_count",),
        ),
        notes=("die = dual M5 Max register pair",),
    )


def m5_ultra_fabric(topology: str = "chain") -> PadFabric:
    """The 4-die M5 Ultra as a pad fabric.

    The protocol aggregates UltraFusion as a die chain (3 x 4.4 TB/s =
    13.2 TB/s); ``topology='full_mesh'`` gives the 6-edge comparison
    layout the elevation gain is measured against.
    """
    links = _make_links(
        pad_edges(M5_ULTRA_DIES, topology),
        kind="ultrafusion",
        bandwidth_bps=ULTRAFUSION_LINK_BPS,
        evidence=TRUTH_SPEC,
    )
    return PadFabric(
        name="apple_m5_ultra",
        pads=tuple(_m5_die(i) for i in range(M5_ULTRA_DIES)),
        links=links,
        topology=topology,
        memory_tiers=(
            MemoryTier(
                "unified_memory",
                "fabric",
                512.0e9,
                1.2e12,
                includes_pad_memory=True,
                evidence=TRUTH_SPEC,
            ),
        ),
        channels=(
            FabricChannel(
                "thunderbolt5",
                TB5_BPS,
                evidence=TRUTH_SPEC,
            ),
            FabricChannel(
                "rdma_cluster",
                M5_ULTRA_DIES * RDMA_TB6_PER_UNIT_BPS,
                evidence=TRUTH_SPEC,
            ),
        ),
        evidence=(
            "dies=4, each a dual M5 Max register pair",
            "ultrafusion 4.4 TB/s per link, 6x connection density vs prev gen",
            "unified memory 512 GB @ 1.2 TB/s",
            "cpu 36 cores = 12 super + 24 performance, zero efficiency cores",
            "neural engine 32 cores, 2x ML capacity; AI speedup 4.5x; render 1.40x",
            "rdma clustering up to 4 units",
        ),
        notes=(
            "H_interconnect vanishes under the unified subspace projection",
            "macOS Hamiltonian treats all dies as one processor",
        ),
    )


def _uniform_pad(index: int, hbm4: bool) -> Pad:
    spec = PadSpec(
        cpu_super_cores=3,
        cpu_performance_cores=6,
        gpu_cores=20,
        neural_engine_cores=8,
        memory_bytes=HBM4_PAD_BYTES if hbm4 else 128.0e9,
        memory_bandwidth_bytes_per_second=HBM4_PAD_BPS if hbm4 else 0.3e12,
        evidence=(
            ("hbm4_3d_stacking",) if hbm4 else ("m5_ultra_per_die_scaled",)
        ),
    )
    return Pad(index=index, label=f"P{index + 1}", spec=spec, role="compute")


def _asymmetric_pad(index: int) -> Pad:
    """Documented asymmetric 10-pad roles.

    P1-P2 master orchestration (12 Super each), P3-P7 compute
    (24 Performance each), P4-P6 double as GPU pads (160 cores each),
    P8-P10 dedicated neural pads (128 NE cores each).
    """
    n = index + 1
    mem = {
        "memory_bytes": 128.0e9,
        "memory_bandwidth_bytes_per_second": 0.3e12,
    }
    if n in (1, 2):
        spec = PadSpec(cpu_super_cores=12, evidence=("asymmetric_orchestration",), **mem)
        role = "orchestration"
    elif n in (8, 9, 10):
        spec = PadSpec(
            neural_engine_cores=128,
            evidence=("dedicated_ai_pad_128_ne",),
            **mem,
        )
        role = "neural_engine"
    else:
        gpu = 160 if n in (4, 5, 6) else 0
        spec = PadSpec(
            cpu_performance_cores=24,
            gpu_cores=gpu,
            evidence=(
                ("dedicated_gpu_pad_160",) if gpu else ("asymmetric_compute",)
            ),
            **mem,
        )
        role = "gpu" if gpu else "compute"
    return Pad(index=index, label=f"P{n}", spec=spec, role=role)


def elevate_pads(
    n_pads: int = 10,
    *,
    topology: str = "full_mesh",
    scheme: str = "uniform",
    interconnect_density: float = 1.0,
    per_pad_hbm4: bool = False,
    reference_pads: int = M5_ULTRA_DIES,
    reference_edges: int = 6,
    reference_log2_dim: int = M5_ULTRA_DIES * PER_PAD_LOG2_HILBERT_DIM,
) -> PadFabric:
    """The N-pad elevation of the M5 Ultra substrate.

    ``scheme='uniform'`` scales the M5 Ultra per-die envelope linearly;
    ``scheme='asymmetric'`` applies the documented role assignment
    (orchestration / compute / dedicated GPU / dedicated neural pads —
    defined for n_pads == 10). ``interconnect_density`` multiplies the
    per-link rate (UltraFusion Gen 3 uses 6.0).
    """
    n = int(n_pads)
    if n < 1:
        raise PadElevationError("n_pads must be >= 1")
    mode = str(scheme).strip().lower()
    if mode == "uniform":
        pads = tuple(_uniform_pad(i, per_pad_hbm4) for i in range(n))
    elif mode == "asymmetric":
        if n != 10:
            raise PadElevationError(
                "asymmetric scheme is defined for the 10-pad layout"
            )
        pads = tuple(_asymmetric_pad(i) for i in range(n))
    else:
        raise PadElevationError(
            f"unknown scheme {scheme!r}; expected 'uniform' or 'asymmetric'"
        )
    density = float(interconnect_density)
    if density <= 0 or not math.isfinite(density):
        raise PadElevationError("interconnect_density must be finite and positive")
    links = _make_links(
        pad_edges(n, topology),
        kind="ultrafusion",
        bandwidth_bps=ULTRAFUSION_LINK_BPS * density,
        evidence=TRUTH_PROJECTION,
    )
    tiers = (
        MemoryTier(
            "hbm4_3d_per_pad" if per_pad_hbm4 else "unified_scaled",
            "pad",
            (HBM4_PAD_BYTES if per_pad_hbm4 else 128.0e9),
            (HBM4_PAD_BPS if per_pad_hbm4 else 0.3e12),
            units=n,
            includes_pad_memory=True,
            evidence=TRUTH_PROJECTION,
        ),
    )
    channels = (
        FabricChannel(
            "rdma_tb6_cluster",
            n * RDMA_TB6_PER_UNIT_BPS,
            evidence=TRUTH_PROJECTION,
        ),
    )
    return PadFabric(
        name=f"m5_elevation_{n}pad_{scheme}_{topology}",
        pads=pads,
        links=links,
        topology=topology,
        memory_tiers=tiers,
        channels=channels,
        evidence=(
            "n-pad elevation over the 4-die M5 Ultra reference",
            f"scheme={mode} topology={topology} density={density}x",
        ),
        notes=(
            "single logical processor via GHZ_n entanglement",
            "cluster state enables measurement-based pad-to-pad teleportation",
        ),
        reference_pads=reference_pads,
        reference_edges=reference_edges,
        reference_log2_dim=reference_log2_dim,
    )


# ---------------------------------------------------------------------------
# Consortium variant
# ---------------------------------------------------------------------------

CONSORTIUM_AXES: Tuple[InstitutionalAxis, ...] = (
    InstitutionalAxis("CERN", "scale + data", "petabyte/s trigger pipelines, radiation-hard silicon, WLCG distributed computing"),
    InstitutionalAxis("MIT", "fabrication + algorithms", "nanofab, superconducting qubits, reversible computing"),
    InstitutionalAxis("Caltech", "quantum + photonics", "trapped ions, photonic interconnects, LIGO-grade metrology"),
    InstitutionalAxis("Princeton", "theory + materials", "topological qubits, quantum error correction, MBE"),
    InstitutionalAxis("Stanford", "systems + AI", "custom accelerators, HBM integration, foundation models"),
    InstitutionalAxis("Oxford", "quantum networking", "distributed entanglement, ion-trap networking, quantum RAM"),
    InstitutionalAxis("Cambridge", "photonics + ML", "silicon photonics, optical compute, statistical mechanics of learning"),
)

#: Deterministic edge-labelling for the consortium full mesh. The protocol
#: names the label set {fiber, free-space optical, superconducting, RDMA,
#: entanglement} but does not fix a per-edge map; this precedence encodes
#: each institution's channel physics.
_CONSORTIUM_LINK_RULES: Tuple[Tuple[str, frozenset], ...] = (
    ("entanglement", frozenset({"Oxford"})),
    ("fiber", frozenset({"CERN"})),
    ("free_space_optical", frozenset({"Caltech", "Cambridge"})),
    ("superconducting", frozenset({"MIT", "Princeton"})),
)

_CONSORTIUM_PAD_DEFS: Tuple[Tuple[int, str, str, PadSpec, Tuple[str, ...]], ...] = (
    (0, "CERN", "data_acquisition_trigger",
     PadSpec(cpu_super_cores=12, memory_bytes=HBM4_PAD_BYTES,
             memory_bandwidth_bytes_per_second=HBM4_PAD_BPS),
     ("wlcg trigger pipeline", "radiation-hard silicon")),
    (1, "MIT", "fabrication_control_algorithms",
     PadSpec(cpu_super_cores=12, memory_bytes=HBM4_PAD_BYTES,
             memory_bandwidth_bytes_per_second=HBM4_PAD_BPS),
     ("nanofab", "reversible computing")),
    (2, "Caltech", "photonic_control_metrology",
     PadSpec(cpu_super_cores=8, cpu_performance_cores=24,
             gpu_photonic_cores=50, memory_bytes=HBM4_PAD_BYTES,
             memory_bandwidth_bytes_per_second=HBM4_PAD_BPS),
     ("photonic interconnects", "photonic tensor cores (shared with Cambridge)")),
    (3, "Princeton", "qec_topological_codes",
     PadSpec(cpu_performance_cores=24, gpu_cores=160,
             memory_bytes=HBM4_PAD_BYTES,
             memory_bandwidth_bytes_per_second=HBM4_PAD_BPS),
     ("topological qubits", "quantum error correction", "dedicated GPU pad")),
    (4, "Stanford", "ai_orchestration",
     PadSpec(cpu_super_cores=8, cpu_performance_cores=16, gpu_cores=160,
             memory_bytes=HBM4_PAD_BYTES,
             memory_bandwidth_bytes_per_second=HBM4_PAD_BPS),
     ("custom accelerators", "foundation models", "dedicated GPU pad")),
    (5, "Oxford", "quantum_networking",
     PadSpec(cpu_performance_cores=24, gpu_cores=160,
             memory_bytes=HBM4_PAD_BYTES,
             memory_bandwidth_bytes_per_second=HBM4_PAD_BPS),
     ("distributed entanglement", "quantum RAM", "dedicated GPU pad")),
    (6, "Cambridge", "optical_compute",
     PadSpec(cpu_performance_cores=16, gpu_photonic_cores=50,
             memory_bytes=HBM4_PAD_BYTES,
             memory_bandwidth_bytes_per_second=HBM4_PAD_BPS),
     ("silicon photonics", "optical compute")),
    (7, "Shared", "federated_ai_cern_collision_data",
     PadSpec(cpu_performance_cores=20, neural_engine_cores=128,
             memory_bytes=HBM4_PAD_BYTES,
             memory_bandwidth_bytes_per_second=HBM4_PAD_BPS),
     ("pure neural engine pad", "trained on CERN collision data")),
    (8, "Shared", "federated_ai_foundation_models",
     PadSpec(cpu_performance_cores=20, neural_engine_cores=128,
             memory_bytes=HBM4_PAD_BYTES,
             memory_bandwidth_bytes_per_second=HBM4_PAD_BPS),
     ("pure neural engine pad", "trained on MIT/Stanford foundation models")),
    (9, "Shared", "federated_ai_quantum_ml",
     PadSpec(cpu_performance_cores=20, neural_engine_cores=128,
             memory_bytes=HBM4_PAD_BYTES,
             memory_bandwidth_bytes_per_second=HBM4_PAD_BPS),
     ("pure neural engine pad", "trained on Oxford/Cambridge quantum ML")),
)


def _consortium_link_kind(a: Pad, b: Pad) -> str:
    inst = {a.institution, b.institution}
    for kind, members in _CONSORTIUM_LINK_RULES:
        if inst & members:
            return kind
    return "rdma_tb6"


def consortium_fabric() -> PadFabric:
    """The CERN x MIT x Caltech x Princeton x Stanford x Oxford x Cambridge
    elevation: 10 institutional pads, full-mesh labelled edges, tiered
    memory, federated neural pads, and the consortium Hamiltonian.

    Link bandwidths stay unallocated — the protocol carries inter-pad
    rates as aggregate backbone channels, so per-edge labels encode
    physics, not numbers.
    """
    pads = tuple(
        Pad(index=i, label=f"P{i + 1}", institution=inst, role=role,
            spec=spec, notes=notes)
        for i, inst, role, spec, notes in _CONSORTIUM_PAD_DEFS
    )
    links = tuple(
        PadLink(
            source=i,
            target=j,
            kind=_consortium_link_kind(pads[i], pads[j]),
            bandwidth_bytes_per_second=None,
            evidence="consortium label set; deterministic assignment",
        )
        for i, j in pad_edges(len(pads), "full_mesh")
    )
    tiers = (
        MemoryTier("on_pad_hbm4", "pad", HBM4_PAD_BYTES, HBM4_PAD_BPS,
                   units=len(pads), includes_pad_memory=True,
                   evidence="consortium tier 0"),
        MemoryTier("consortium_dram", "fabric", 20.0e12, 40.0e12,
                   evidence="consortium tier 1"),
        MemoryTier("cern_wlcg", "external", 1.0e18, 1.0e16,
                   evidence="consortium tier 2"),
        MemoryTier("quantum_ram_oxford", "coherent", None, None,
                   coherent=True, evidence="consortium tier 3: D^10 coherent"),
    )
    channels = (
        FabricChannel("optical_intersite_mesh", OPTICAL_INTERPAD_BPS,
                      evidence="Caltech/Cambridge photonic backbone"),
        FabricChannel("cern_wlcg_trigger", CERN_WLCG_TRIGGER_BPS,
                      evidence="CERN WLCG trigger link"),
        FabricChannel("rdma_tb6_cluster", len(pads) * RDMA_TB6_PER_UNIT_BPS,
                      evidence="RDMA over Thunderbolt 6"),
        FabricChannel("quantum_entanglement", None, coherent=True,
                      evidence="Oxford distributed entanglement channel"),
    )
    institutional_terms = (
        "H_CERN_trigger", "H_MIT_fabrication", "H_Caltech_photonics",
        "H_Princeton_QEC", "H_Stanford_AI", "H_Oxford_entanglement",
        "H_Cambridge_optical",
    )
    fabric = PadFabric(
        name="consortium_10pad",
        pads=pads,
        links=links,
        topology="full_mesh",
        memory_tiers=tiers,
        channels=channels,
        evidence=(
            "seven-institution consortium elevation over the M5 10-pad protocol",
            "edges labelled by channel physics; rates carried by channels",
        ),
        notes=(
            "institutional GHZ_7 entangles the named-institution pads",
            "federated learning across neural pads: grad L = sum grad L_i (secure aggregation)",
            "amdahl f_serial dominated by peer-review latency, not compute",
            "institutional hamiltonian terms: " + ", ".join(institutional_terms),
        ),
        reference_pads=M5_ULTRA_DIES,
        reference_edges=6,
        reference_log2_dim=M5_ULTRA_DIES * PER_PAD_LOG2_HILBERT_DIM,
    )
    return fabric


# ---------------------------------------------------------------------------
# Documented tables
# ---------------------------------------------------------------------------

def quantum_formulation_map() -> Tuple[Dict[str, str], ...]:
    """Classical feature -> quantum formulation (M5 Ultra section 11)."""
    return (
        {"classical": "dual-die M5 Max x2", "quantum": "|Psi> = tensor of 4 die registers (8 M5 Max subunits)"},
        {"classical": "UltraFusion", "quantum": "entanglement channel |Phi+> per die pair"},
        {"classical": "4.4 TB/s inter-die", "quantum": "B_inter = 4.4e12 qubits/s"},
        {"classical": "512 GB unified memory", "quantum": "N_memory = 4.4e12 qubits (8 per byte)"},
        {"classical": "1.2 TB/s memory BW", "quantum": "B_mem = 1.2e12 qubit-transfers/s"},
        {"classical": "36 CPU cores", "quantum": "|CPU> = (1/sqrt(36)) sum |Core_k>"},
        {"classical": "GPU neural accelerators", "quantum": "U_NA = exp(-i H_NA t/hbar) per GPU core"},
        {"classical": "32-core Neural Engine", "quantum": "H_NE = sum_{k=1}^{32} H_NE^(k)"},
        {"classical": "Thunderbolt 5", "quantum": "H_TB5 = sum g_k (a_k+ b_k + h.c.)"},
        {"classical": "RDMA clustering", "quantum": "H_RDMA = sum J_ij (sigma_i+ sigma_j- + h.c.)"},
        {"classical": "unified processor", "quantum": "P_unified H_interconnect P_unified = 0"},
        {"classical": "macOS sees 4 dies as 1", "quantum": "[H_macOS, H_interconnect] = 0"},
    )


def m5_ultra_expectation_values() -> Tuple[Dict[str, Any], ...]:
    """Performance metrics as quantum expectation values (section 9)."""
    return (
        {"metric": "inter_die_bandwidth", "classical": "4.4 TB/s", "expectation": 4.4e12},
        {"metric": "memory_qubits", "classical": "512 GB", "expectation": 4.4e12},
        {"metric": "memory_bandwidth", "classical": "1.2 TB/s", "expectation": 1.2e12},
        {"metric": "cpu_cores", "classical": 36, "expectation": 36},
        {"metric": "ai_speedup", "classical": "4.5x", "expectation": 4.5},
        {"metric": "render_improvement", "classical": "+40%", "expectation": 1.40},
        {"metric": "neural_engine_cores", "classical": 32, "expectation": 32},
        {"metric": "thunderbolt5", "classical": "present", "expectation": "H_TB5 != 0"},
        {"metric": "rdma_cluster_units", "classical": 4, "expectation": 4},
    )


ELEVATION_STRATEGIES_10PAD: Tuple[ElevationStrategy, ...] = (
    ElevationStrategy(1, "full-mesh UltraFusion", "7.5x interconnect", "very_high"),
    ElevationStrategy(2, "dedicated AI pads (P8-P10)", "12x NE compute", "medium"),
    ElevationStrategy(3, "dedicated GPU pads (P4-P6)", "6x GPU", "medium"),
    ElevationStrategy(4, "asymmetric master pads", "2x orchestration", "low"),
    ElevationStrategy(5, "HBM4 3D stacking", "6.7x memory bandwidth", "high"),
    ElevationStrategy(6, "Thunderbolt 6 RDMA", "10x cluster", "low"),
    ElevationStrategy(7, "optical inter-pad links", "100x bandwidth", "very_high"),
    ElevationStrategy(8, "photonic entanglement", "unbounded coherence", "theoretical"),
)

CONSORTIUM_STRATEGIES: Tuple[ElevationStrategy, ...] = (
    ElevationStrategy(1, "full-mesh optical UltraFusion", "7.5x interconnect", "very_high", "Caltech + Cambridge"),
    ElevationStrategy(2, "dedicated AI pads", "12x NE compute", "medium", "Stanford"),
    ElevationStrategy(3, "photonic tensor cores", "100x GPU", "very_high", "Cambridge"),
    ElevationStrategy(4, "topological QEC", "1e6x error suppression", "high", "Princeton"),
    ElevationStrategy(5, "distributed entanglement", "unbounded coherence", "theoretical", "Oxford"),
    ElevationStrategy(6, "CERN trigger pipeline", "10 PB/s ingest", "medium", "CERN"),
    ElevationStrategy(7, "radiation-hard silicon", "100x uptime", "medium", "CERN + MIT"),
    ElevationStrategy(8, "HBM4 3D stacking", "6.7x memory bandwidth", "high", "MIT + Stanford"),
)


__all__ = [
    "CONSORTIUM_AXES",
    "CONSORTIUM_STRATEGIES",
    "ELEVATION_STRATEGIES_10PAD",
    "ElevationStrategy",
    "FabricChannel",
    "HamiltonianTerm",
    "InstitutionalAxis",
    "LINK_BANDWIDTHS_BPS",
    "M5MAX_SUBUNITS_PER_DIE",
    "M5_AI_SPEEDUP",
    "M5_RENDER_FACTOR",
    "M5_ULTRA_DIES",
    "MemoryTier",
    "MESH10_EDGES",
    "Pad",
    "PadElevationError",
    "PadFabric",
    "PadLink",
    "PadSpec",
    "PER_PAD_LOG2_HILBERT_DIM",
    "TOPOLOGIES",
    "ULTRAFUSION_GEN3_DENSITY",
    "ULTRAFUSION_LINK_BPS",
    "consortium_fabric",
    "elevate_pads",
    "m5_ultra_expectation_values",
    "m5_ultra_fabric",
    "pad_edges",
    "quantum_formulation_map",
]

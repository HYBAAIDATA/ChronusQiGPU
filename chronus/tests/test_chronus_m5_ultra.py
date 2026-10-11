"""Contract tests for the M5-class multi-pad substrate elevation model."""
from __future__ import annotations

import json
import math

import pytest

from chronus import m5_ultra as m5
from chronus.m5_ultra import (
    CONSORTIUM_AXES,
    CONSORTIUM_STRATEGIES,
    ELEVATION_STRATEGIES_10PAD,
    MESH10_EDGES,
    PadElevationError,
    consortium_fabric,
    elevate_pads,
    m5_ultra_expectation_values,
    m5_ultra_fabric,
    pad_edges,
    quantum_formulation_map,
)


# ---------------------------------------------------------------------------
# Topology
# ---------------------------------------------------------------------------

def test_chain_and_ring_edges():
    assert pad_edges(4, "chain") == ((0, 1), (1, 2), (2, 3))
    assert pad_edges(4, "ring") == ((0, 1), (1, 2), (2, 3), (3, 0))
    assert pad_edges(10, "chain") == tuple((i, i + 1) for i in range(9))


def test_full_mesh_edges():
    assert len(pad_edges(4, "full_mesh")) == 6
    assert len(pad_edges(10, "full_mesh")) == 45


def test_mesh10_lattice_has_documented_15_edges():
    edges = pad_edges(10, "mesh")
    assert edges == MESH10_EDGES
    assert len(edges) == 15
    assert len(set(edges)) == 15
    assert all(i < j for i, j in edges)


def test_mesh_rejects_noncanonical_pad_counts():
    with pytest.raises(PadElevationError):
        pad_edges(4, "mesh")
    with pytest.raises(PadElevationError):
        pad_edges(0, "chain")
    with pytest.raises(PadElevationError):
        pad_edges(4, "nonsense")


# ---------------------------------------------------------------------------
# M5 Ultra baseline
# ---------------------------------------------------------------------------

def test_m5_ultra_classical_totals():
    fab = m5_ultra_fabric()
    assert fab.n_pads == 4
    assert fab.cpu_super_cores == 12
    assert fab.cpu_performance_cores == 24
    assert fab.cpu_efficiency_cores == 0
    assert fab.cpu_cores == 36
    assert fab.gpu_cores == 80
    assert fab.neural_engine_cores == 32
    assert fab.memory_bytes == pytest.approx(512e9)
    assert fab.memory_bandwidth_bps == pytest.approx(1.2e12)
    assert fab.ai_speedup_peak == pytest.approx(4.5)


def test_m5_ultra_interconnect_chain_aggregate():
    fab = m5_ultra_fabric("chain")
    assert fab.n_links == 3
    # 3 UltraFusion links + TB5 + 4-unit RDMA channels
    assert fab.interconnect_bandwidth_bps == pytest.approx(
        3 * 4.4e12 + 15.0e9 + 4 * 15.0e9
    )


def test_m5_ultra_quantum_formulation():
    fab = m5_ultra_fabric()
    assert fab.n_registers == 8  # 4 dies x 2 M5 Max subunits
    assert fab.hilbert_log2_dim == 512  # 8 x 64
    assert "GHZ_4" in fab.ghz_state
    assert fab.quantum_block()["unified_projection"] == "[P_unified, H_fabric] = 0"
    terms = {t.name for t in fab.hamiltonian_terms()}
    assert any("H_link_ultrafusion" in t for t in terms)
    assert any("H_channel_rdma_cluster" in t for t in terms)


def test_m5_ultra_truth_labels():
    fab = m5_ultra_fabric()
    assert fab.measured_by_chronus is False
    assert fab.truth_class == "quantum_substrate_formulation"


def test_m5_ultra_documented_tables():
    mapping = quantum_formulation_map()
    assert len(mapping) == 12
    assert any("Phi+" in row["quantum"] for row in mapping)
    ev = m5_ultra_expectation_values()
    assert len(ev) == 9
    by_metric = {row["metric"]: row["expectation"] for row in ev}
    assert by_metric["cpu_cores"] == 36
    assert by_metric["neural_engine_cores"] == 32
    assert by_metric["rdma_cluster_units"] == 4


def test_m5_ultra_amdahl_cluster():
    fab = m5_ultra_fabric()
    assert fab.amdahl_bound(0.0) == pytest.approx(4.0)
    assert fab.amdahl_bound(1.0) == pytest.approx(1.0)
    assert fab.amdahl_bound(0.5) == pytest.approx(1.0 / (0.5 + 0.5 / 4))


# ---------------------------------------------------------------------------
# 10-pad elevation (uniform)
# ---------------------------------------------------------------------------

def test_elevate_10pad_mesh_counts():
    fab = elevate_pads(10, topology="mesh")
    assert fab.n_links == 15
    assert fab.topology_gain_vs_reference == pytest.approx(15 / 6)


def test_elevate_10pad_full_mesh_counts():
    fab = elevate_pads(10, topology="full_mesh")
    assert fab.n_links == 45
    assert fab.topology_gain_vs_reference == pytest.approx(7.5)


def test_elevate_10pad_bandwidth_scaling():
    fab = elevate_pads(10, topology="full_mesh")
    # 45 links x 4.4 TB/s = 198 TB/s + RDMA channel
    assert fab.interconnect_bandwidth_bps == pytest.approx(
        198.0e12 + 10 * 15.0e9
    )
    gen3 = elevate_pads(10, topology="full_mesh", interconnect_density=6.0)
    assert gen3.interconnect_bandwidth_bps == pytest.approx(
        45 * 4.4e12 * 6.0 + 10 * 15.0e9
    )  # ~1.2 PB/s link bandwidth


def test_elevate_10pad_memory_and_cores():
    fab = elevate_pads(10)
    assert fab.memory_bytes == pytest.approx(1.28e12)
    assert fab.memory_bandwidth_bps == pytest.approx(3.0e12)
    assert fab.cpu_cores == 90
    assert fab.cpu_super_cores == 30
    assert fab.cpu_performance_cores == 60
    assert fab.neural_engine_cores == 80
    assert fab.gpu_cores == 200


def test_elevate_10pad_hbm4_option():
    fab = elevate_pads(10, per_pad_hbm4=True)
    assert fab.memory_bytes == pytest.approx(10 * 2.0e12)
    assert fab.memory_bandwidth_bps == pytest.approx(10 * 8.0e12)


def test_elevate_hilbert_space_growth():
    fab = elevate_pads(10)
    assert fab.hilbert_log2_dim == 640
    assert fab.hilbert_log2_gain_vs_reference == 384
    log10 = 384 * math.log10(2)
    assert log10 == pytest.approx(115.6, abs=0.1)


def test_elevate_quantum_descriptors():
    fab = elevate_pads(10, topology="full_mesh")
    q = fab.quantum_block()
    assert q["n_pads"] == 10
    assert "GHZ_10" in q["ghz_state"]
    assert q["cluster_state_edges"] == 45
    assert q["born_rule"] == "P(k) = |alpha_k|^2"


def test_elevate_amdahl_bound():
    fab = elevate_pads(10)
    assert fab.amdahl_bound(0.0) == pytest.approx(10.0)
    assert fab.amdahl_bound(0.1) == pytest.approx(1.0 / (0.1 + 0.9 / 10))
    with pytest.raises(PadElevationError):
        fab.amdahl_bound(1.5)


def test_elevation_strategy_tables():
    assert len(ELEVATION_STRATEGIES_10PAD) == 8
    gains = {s.strategy: s.gain for s in ELEVATION_STRATEGIES_10PAD}
    assert gains["full-mesh UltraFusion"] == "7.5x interconnect"
    assert gains["HBM4 3D stacking"] == "6.7x memory bandwidth"


# ---------------------------------------------------------------------------
# 10-pad elevation (asymmetric)
# ---------------------------------------------------------------------------

def test_elevate_asymmetric_roles():
    fab = elevate_pads(10, scheme="asymmetric")
    assert fab.cpu_super_cores == 24       # P1-P2 x 12
    assert fab.cpu_performance_cores == 120  # P3-P7 x 24
    assert fab.gpu_cores == 480            # P4-P6 x 160
    assert fab.neural_engine_cores == 384  # P8-P10 x 128
    assert fab.ai_speedup_peak == pytest.approx(54.0)  # 4.5 x (384/32)
    roles = {p.label: p.role for p in fab.pads}
    assert roles["P1"] == "orchestration"
    assert roles["P5"] == "gpu"
    assert roles["P10"] == "neural_engine"


def test_elevate_asymmetric_requires_10_pads():
    with pytest.raises(PadElevationError):
        elevate_pads(8, scheme="asymmetric")
    with pytest.raises(PadElevationError):
        elevate_pads(10, scheme="bogus")
    with pytest.raises(PadElevationError):
        elevate_pads(10, interconnect_density=0)


# ---------------------------------------------------------------------------
# Consortium elevation
# ---------------------------------------------------------------------------

def test_consortium_pads_and_institutions():
    fab = consortium_fabric()
    assert fab.n_pads == 10
    inst = {p.institution for p in fab.pads}
    assert inst == {
        "CERN", "MIT", "Caltech", "Princeton",
        "Stanford", "Oxford", "Cambridge", "Shared",
    }
    assert len(CONSORTIUM_AXES) == 7


def test_consortium_links_are_full_mesh_and_labelled():
    fab = consortium_fabric()
    assert fab.n_links == 45
    kinds = set(fab.links_by_kind)
    assert kinds <= {
        "fiber", "free_space_optical", "superconducting", "rdma_tb6", "entanglement",
    }
    assert "entanglement" in kinds  # Oxford-labelled coherent links
    assert "fiber" in kinds         # CERN-labelled links


def test_consortium_heterogeneous_cores():
    fab = consortium_fabric()
    assert fab.cpu_cores == 204
    assert fab.cpu_super_cores == 40       # 12+12+8+8
    assert fab.cpu_performance_cores == 164
    assert fab.gpu_cores == 480            # Princeton+Stanford+Oxford x160
    assert fab.gpu_photonic_cores == 100   # Caltech+Cambridge x50
    assert fab.neural_engine_cores == 384  # Shared pads x128
    assert fab.ai_speedup_peak == pytest.approx(54.0)


def test_consortium_memory_tiers():
    fab = consortium_fabric()
    tiers = {t.name: t for t in fab.memory_tiers}
    assert tiers["on_pad_hbm4"].total_capacity_bytes == pytest.approx(20.0e12)
    assert tiers["consortium_dram"].capacity_bytes == pytest.approx(20.0e12)
    assert tiers["cern_wlcg"].capacity_bytes == pytest.approx(1.0e18)
    qram = tiers["quantum_ram_oxford"]
    assert qram.coherent and qram.capacity_bytes is None
    assert fab.total_addressable_memory_bytes == pytest.approx(
        20.0e12 + 20.0e12 + 1.0e18
    )


def test_consortium_bandwidth_channels():
    fab = consortium_fabric()
    chans = {c.name: c for c in fab.channels}
    assert chans["optical_intersite_mesh"].bandwidth_bytes_per_second == 1.2e15
    assert chans["cern_wlcg_trigger"].bandwidth_bytes_per_second == 1.0e16
    assert chans["rdma_tb6_cluster"].bandwidth_bytes_per_second == 1.5e11
    ent = chans["quantum_entanglement"]
    assert ent.coherent and ent.bandwidth_bytes_per_second is None
    # ~11.35 PB/s aggregate; link rates stay unallocated to avoid
    # double counting against the channel aggregates.
    assert fab.interconnect_bandwidth_bps == pytest.approx(
        1.2e15 + 1.0e16 + 1.5e11
    )


def test_consortium_quantum_and_hamiltonian():
    fab = consortium_fabric()
    q = fab.quantum_block()
    assert q["hilbert_log2_dim"] == 640
    assert "GHZ_10" in q["ghz_state"]
    assert q["cluster_state_edges"] == 45
    text = " ".join(fab.notes)
    assert "GHZ_7" in text
    assert "H_Oxford_entanglement" in text
    assert "secure aggregation" in text
    assert "peer-review latency" in text


def test_consortium_strategies_table():
    assert len(CONSORTIUM_STRATEGIES) == 8
    lead = {s.strategy: s.lead for s in CONSORTIUM_STRATEGIES}
    assert lead["topological QEC"] == "Princeton"
    assert lead["distributed entanglement"] == "Oxford"


def test_consortium_truth_labels():
    fab = consortium_fabric()
    assert fab.measured_by_chronus is False
    assert fab.truth_class == "quantum_substrate_formulation"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "fab",
    [
        m5_ultra_fabric(),
        elevate_pads(10),
        elevate_pads(10, topology="mesh", scheme="asymmetric"),
        consortium_fabric(),
    ],
    ids=["m5_ultra", "uniform_10", "asymmetric_10_mesh", "consortium"],
)
def test_fabric_serializes_and_fingerprints(fab):
    payload = fab.as_dict()
    blob = json.dumps(payload)  # must be JSON-safe
    assert fab.fingerprint in payload["fingerprint"]
    assert len(fab.fingerprint) == 64
    assert payload["measured_by_chronus"] is False

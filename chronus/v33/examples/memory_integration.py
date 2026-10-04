#!/usr/bin/env python3
"""
Chronos GPU v3.3 — Full Memory System Integration Script
========================================================

Anchor: Quantum theory stems from mathematics.
        Substrate- and hardware-agnostic. Fully computable.

Demonstrates:
  L0 Table → L1 NeuralIndex → L2 MPSStore → L3 QRAM
  → BlockEncode → QSVT
  → ChronosEngine.render / render_spectral

Run from the monorepo root:
  PYTHONPATH=. python chronus/v33/examples/memory_integration.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running without install (monorepo: repo root on path, not backup-era src/)
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import numpy as np

from chronus.v33 import ChronosEngine, __version__
from chronus.v33.memory import (
    Table,
    QRAM,
    MPSStore,
    NeuralCombineMemory,
    MemoryHierarchy,
    Poly,
    apply_qsvt,
    qsvt_from_block_enc,
    block_encode,
    Structure,
    prepare_select,
    run_memory_self_tests,
    memory_status,
)


SMOKE_SCENE = """
scene smoke {
  manifold M32
  object sphere {
    geometry sphere(radius=1.0, center=(0,0,0))
    material glass {
      dielectric = 1.5
      absorption = 0.001
      quantum { resonance = [0.5] }
    }
  }
  light sun {
    type = directional
    position = (1,1,1)
    intensity = 1.0
    driving = zero()
  }
  camera {
    resolution = (160, 90)
    fov = 60.0
    position = (0, 0, 5)
    readout = { observables = [intensity, depth, normal] }
  }
  quality {
    layers = 2
    evolution_steps = 20
    learning_rate = 0.08
    damping = 0.01
    seed = 0
  }
}
"""


def section(title: str) -> None:
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def main() -> None:
    print(f"Chronos GPU {__version__}")
    print("Anchor: Quantum theory stems from mathematics.")
    print("        Substrate- and hardware-agnostic.")

    # ------------------------------------------------------------------
    # 1. Self-tests
    # ------------------------------------------------------------------
    section("1. Memory subsystem self-tests")
    results = run_memory_self_tests()
    for name, msg in results.items():
        print(f"  {name}: {msg}")
    assert all(m.endswith("PASS") for m in results.values())

    # ------------------------------------------------------------------
    # 2. L0 Table + L3 QRAM
    # ------------------------------------------------------------------
    section("2. L0 Table + L3 QRAM (unitary oracle)")
    table = Table.from_integers([3, 1, 4, 1, 5, 9, 2, 6], domain_bits=3, value_bits=4)
    qram = QRAM(table)
    print(f"  dimension = 2^({qram.domain_bits}+{qram.value_bits}) = {qram.dimension}")
    for addr in range(4):
        _, bus = qram.apply_basis(addr, 0)
        print(f"  U_f |{addr}⟩|0⟩ → |{addr}⟩|{bus}⟩  (table[{addr}]={table.lookup_int(addr)})")
    # Self-inverse check
    a, b = qram.apply_basis(2, 0)
    a2, b2 = qram.apply_basis(a, b)
    assert (a2, b2) == (2, 0)
    print("  self-inverse: OK")

    # ------------------------------------------------------------------
    # 3. L2 MPSStore
    # ------------------------------------------------------------------
    section("3. L2 MPSStore (tensor-train state memory)")
    store = MPSStore(n_qubits=12, bond_dim=16)
    trunc = store.load_ghz()
    audit = store.audit()
    print(f"  qubits            = {audit.n_qubits}")
    print(f"  bond_dim          = {audit.bond_dim}")
    print(f"  mps_parameters    = {audit.mps_parameter_count}")
    print(f"  dense_amplitudes  = {audit.dense_amplitude_count:.3e}")
    print(f"  compression_ratio = {audit.compression_ratio:.3e}")
    print(f"  is_compressed     = {audit.is_compressed}")
    print(f"  mid-bond entropy  = {audit.entanglement_entropy_mid:.6f}")
    print(f"  truncation_error  = {trunc}")
    assert audit.is_compressed and trunc == 0.0

    # ------------------------------------------------------------------
    # 4. L1 Neural index
    # ------------------------------------------------------------------
    section("4. L1 NeuralCombine (MLP router)")
    neural = NeuralCombineMemory(n_slots=8, address_bits=6, value_bits=4, n_hidden=32, seed=0)
    report = neural.train_router(epochs=50, seed=0)
    print(f"  final_loss     = {report.final_loss:.6f}")
    print(f"  accuracy_top1  = {report.accuracy_top1:.4f}")
    print(f"  n_slots        = {report.n_slots}")
    neural.write(7, 42)
    val, weights = neural.read(7)
    print(f"  soft-read(7)   = {val:.3f}  weights_sum={weights.sum():.6f}")

    # ------------------------------------------------------------------
    # 5. BlockEncode + QSVT
    # ------------------------------------------------------------------
    section("5. BlockEncode → QSVT")
    X = np.array([[0, 1], [1, 0]], dtype=complex)
    Z = np.array([[1, 0], [0, -1]], dtype=complex)
    U_A, alpha = prepare_select(np.array([0.6, 0.4]), [X, Z], system_dim=2)
    from chronus.v33.memory.block_encode import BlockEnc
    be = BlockEnc(alpha=alpha, ancilla_bits=1, unitary=U_A, n_system=2, semantic_name="demo_LCU")
    print(f"  BlockEnc alpha={be.alpha}  unitary shape={U_A.shape}")

    res_t2 = qsvt_from_block_enc(be, kind="chebyshev", degree=2)
    print(f"  QSVT Chebyshev T2: {res_t2.semantic}")
    print(f"    phases = {len(res_t2.phases)}  top_left shape = {res_t2.top_left_block.shape}")
    assert res_t2.unitary is not None
    err = np.max(np.abs(res_t2.unitary.conj().T @ res_t2.unitary - np.eye(res_t2.unitary.shape[0])))
    print(f"    unitarity residual = {err:.2e}")

    res_exp = qsvt_from_block_enc(be, kind="exp_cosine", t=0.5, degree=4)
    print(f"  QSVT exp_cosine: {res_exp.semantic}  parity={res_exp.poly.parity}")

    # ------------------------------------------------------------------
    # 6. Full MemoryHierarchy
    # ------------------------------------------------------------------
    section("6. MemoryHierarchy (L0→L1→L2→L3→QSVT)")
    hier = MemoryHierarchy(
        address_bits=8,
        value_bits=8,
        n_slots=8,
        mps_qubits=12,
        mps_bond_dim=16,
        seed=0,
    )
    for i in range(32):
        hier.write(i, (i * 7 + 3) % 256)
    print(f"  L0 read(10) = {hier.read(10)}")
    addr, bus = hier.coherent_query(10)
    print(f"  L3 coherent_query(10) → addr={addr} bus={bus}")
    hier.load_ghz_into_mps()
    neural_rep = hier.train_neural_index(epochs=40)
    print(f"  L1 router accuracy = {neural_rep.accuracy_top1:.4f}")
    qsvt_res = hier.qsvt(kind="chebyshev", degree=2, sparsity=2)
    print(f"  QSVT = {qsvt_res.semantic}")
    status = memory_status(address_bits=6, mps_qubits=12, mps_bond_dim=16)
    print("  memory_status (compact):")
    print(json.dumps({k: status[k] for k in ("hierarchy", "mps", "qsvt")}, indent=4))

    # ------------------------------------------------------------------
    # 7. ChronosEngine integration
    # ------------------------------------------------------------------
    section("7. ChronosEngine — baseline vs spectral")
    eng = ChronosEngine(
        n_faces=32,
        layers=2,
        enable_memory=True,
        memory_mps_qubits=8,
        memory_mps_bond_dim=8,
    )

    base = eng.render(SMOKE_SCENE)
    print(f"  baseline  energy={base.energy:.6f}  spectral={base.spectral_mode}")
    print(f"            pixels={base.rendered_pixels_hit}/{base.total_pixels}")

    spec = eng.render_spectral(
        SMOKE_SCENE,
        qsvt_kind="chebyshev",
        qsvt_degree=2,
        sparsity=2,
    )
    print(f"  spectral  energy={spec.energy:.6f}  spectral={spec.spectral_mode}")
    print(f"            qsvt={spec.qsvt_semantic}")
    print(f"            mem_compression={spec.memory_compression_ratio}")
    print(f"            dist_sum={spec.distribution.sum():.6f}")
    print(f"            pixels={spec.rendered_pixels_hit}/{spec.total_pixels}")

    assert abs(base.energy - spec.energy) < 1e-9, "energy must be invariant"
    assert spec.spectral_mode is True
    assert eng.memory is not None
    print()
    print("  Energy invariant: OK")
    print("  Memory hierarchy attached: OK")

    # ------------------------------------------------------------------
    # Done
    # ------------------------------------------------------------------
    section("DONE")
    print("All layers exercised. Integration complete.")
    print(f"Access hierarchy via:  eng.memory")
    print(f"Re-run self-tests via: run_memory_self_tests()")


if __name__ == "__main__":
    main()

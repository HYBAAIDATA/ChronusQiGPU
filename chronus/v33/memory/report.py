"""
Memory subsystem end-to-end report and self-tests.
"""
from __future__ import annotations

from typing import Any, Dict

from .table import _self_test as table_st
from .qram import _self_test as qram_st
from .block_encode import _self_test as block_st
from .mps_store import _self_test as mps_st
from .neural_combine import _self_test as neural_st
from .qsvt import _self_test as qsvt_st
from .hierarchy import _self_test as hier_st, MemoryHierarchy


def run_memory_self_tests() -> Dict[str, str]:
    return {
        "table": table_st(),
        "qram": qram_st(),
        "block_encode": block_st(),
        "mps_store": mps_st(),
        "neural_combine": neural_st(),
        "qsvt": qsvt_st(),
        "hierarchy": hier_st(),
    }


def memory_status(
    address_bits: int = 8,
    mps_qubits: int = 32,
    mps_bond_dim: int = 32,
) -> Dict[str, Any]:
    """Build a hierarchy, exercise every layer, return a real numeric report."""
    hier = MemoryHierarchy(
        address_bits=address_bits,
        value_bits=8,
        n_slots=8,
        mps_qubits=mps_qubits,
        mps_bond_dim=mps_bond_dim,
        seed=0,
    )
    for i in range(min(64, 1 << address_bits)):
        hier.write(i, (i * 7 + 3) % 256)
    for i in range(16):
        hier.read(i)
        hier.coherent_query(i)
    trunc = hier.load_ghz_into_mps()
    neural = hier.train_neural_index(epochs=50)
    be = hier.block_encode_from_l0(sparsity=4, system_dim=2)
    qsvt_res = hier.qsvt(kind="chebyshev", degree=2, sparsity=2, system_dim=2)
    rep = hier.report()
    return {
        "self_tests": run_memory_self_tests(),
        "hierarchy": {
            "l0_hits": rep.l0_hits,
            "l1_hits": rep.l1_hits,
            "l2_queries": rep.l2_queries,
            "l3_queries": rep.l3_queries,
            "total_reads": rep.total_reads,
        },
        "neural": {
            "final_loss": neural.final_loss,
            "accuracy_top1": neural.accuracy_top1,
            "n_slots": neural.n_slots,
        },
        "mps": {
            "n_qubits": rep.mps_audit.n_qubits if rep.mps_audit else 0,
            "compression_ratio": rep.mps_audit.compression_ratio if rep.mps_audit else 0.0,
            "is_compressed": rep.mps_audit.is_compressed if rep.mps_audit else False,
            "entanglement_entropy_mid": rep.mps_audit.entanglement_entropy_mid if rep.mps_audit else 0.0,
            "max_truncation_error": trunc,
        },
        "block_encode": {
            "alpha": be.alpha,
            "unitary_shape": list(be.unitary.shape) if be.unitary is not None else None,
            "semantic": be.semantic_name,
        },
        "qsvt": {
            "semantic": qsvt_res.semantic,
            "degree": qsvt_res.poly.degree,
            "n_phases": len(qsvt_res.phases),
            "unitary_shape": list(qsvt_res.unitary.shape) if qsvt_res.unitary is not None else None,
            "top_left_shape": list(qsvt_res.top_left_block.shape) if qsvt_res.top_left_block is not None else None,
        },
    }


if __name__ == "__main__":
    import json
    tests = run_memory_self_tests()
    for k, v in tests.items():
        print(f"  {k}: {v}")
    status = memory_status(mps_qubits=12, mps_bond_dim=16)
    print(json.dumps({k: status[k] for k in ("hierarchy", "neural", "mps", "block_encode", "qsvt")}, indent=2))

"""
Chronos GPU Memory Subsystem
============================

Anchor
------
Quantum theory stems from mathematics. It is substrate- and hardware-agnostic.
Every object below is pure linear algebra and classical data structures;
nothing depends on a physical qubit technology.

Architecture (mathematical)
---------------------------
  L0  Table          classical finite map  {0,1}^n → {0,1}^k
  L1  NeuralIndex    small trainable MLP router (real backprop, measured loss)
  L2  MPSStore       Matrix Product State / tensor-train state memory
  L3  QRAM           unitary oracle  U_f |x⟩|y⟩ = |x⟩|y ⊕ f(x)⟩
       │
       ├─ BlockEncode (PREPARE + SELECT) → BlockEnc
       └─ QSVT       polynomial singular-value transform of BlockEnc

Public API
----------
  Table, QRAM, BlockEnc, MPSStore, NeuralCombineMemory,
  Poly, QSVTResult, apply_qsvt, qsvt_from_block_enc,
  MemoryHierarchy, run_memory_self_tests, memory_status
"""

from .table import Table, Bitstring
from .qram import QRAM, qram_apply
from .block_encode import Structure, BlockEnc, block_encode, prepare_select
from .mps_store import MPSStore, MemoryAudit
from .neural_combine import NeuralCombineMemory, NeuralIndexReport
from .qsvt import Poly, QSVTResult, apply_qsvt, qsvt_from_block_enc
from .hierarchy import MemoryHierarchy, HierarchyReport
from .report import run_memory_self_tests, memory_status

__all__ = [
    "Table",
    "Bitstring",
    "QRAM",
    "qram_apply",
    "Structure",
    "BlockEnc",
    "block_encode",
    "prepare_select",
    "MPSStore",
    "MemoryAudit",
    "NeuralCombineMemory",
    "NeuralIndexReport",
    "Poly",
    "QSVTResult",
    "apply_qsvt",
    "qsvt_from_block_enc",
    "MemoryHierarchy",
    "HierarchyReport",
    "run_memory_self_tests",
    "memory_status",
]

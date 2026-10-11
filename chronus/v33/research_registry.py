"""Executable, source-linked intake for quantum-computing methods.

A passing case means only that the named method-level invariant passes in this
repository.  It does not claim experimental replication, hardware advantage,
or validation of every conclusion in the cited publication.

Two families are registered:

``ACADEMIC_CASES``
    The Chronos v3.3 intake: published methods checked against the in-tree
    ``chronus.v33`` implementations.

``PRODUCT_BOUNDARY_CASES``
    The Turing VQC product boundary: the exactness, parity and refusal
    invariants the shipped virtual quantum computer asserts.  Those nodes live
    inside the package, so they are addressed from the repository root as
    ``turing_universal_quantum_computer/tests/...``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

_REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ResearchCase:
    key: str
    title: str
    institutions: tuple[str, ...]
    source_url: str
    implementation: str
    invariant: str
    test_node: str

    def as_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["institutions"] = list(self.institutions)
        value["command"] = f"python -m pytest -q {self.test_node}"
        return value


ACADEMIC_CASES: tuple[ResearchCase, ...] = (
    ResearchCase(
        key="qaoa-reference",
        title="A Quantum Approximate Optimization Algorithm",
        institutions=("MIT",),
        source_url="https://arxiv.org/abs/1411.4028",
        implementation="chronus.v33.academic.nist.NIST_Benchmark",
        invariant="p=1 two-vertex MaxCut QAOA cost reduction is positive",
        test_node="chronus/tests/test_chronus_v33/test_academic.py::test_nist_benchmark_determinism_score",
    ),
    ResearchCase(
        key="surface-code-single-error",
        title="Surface codes: Towards practical large-scale quantum computation",
        institutions=("University of California, Santa Barbara",),
        source_url="https://arxiv.org/abs/1208.0928",
        implementation="chronus.v33.academic.caltech.Caltech_Surface_Code",
        invariant="distance-3 reference decoder corrects a single injected Pauli error",
        test_node="chronus/tests/test_chronus_v33/test_academic.py::test_surface_code_decodes_single_error",
    ),
    ResearchCase(
        key="tensor-network-bell",
        title="Tensor-network quantum-circuit simulation",
        institutions=("University research implementations",),
        source_url="https://arxiv.org/abs/2310.03978",
        implementation="chronus.v33.academic.tensor_compression.MatrixProductState",
        invariant="Bell-state dense reconstruction and one-bit cut entropy agree",
        test_node="chronus/tests/test_chronus_v33/test_academic.py::test_mps_bell_state",
    ),
    ResearchCase(
        key="qsvt-unitarity",
        title="Quantum singular value transformation and beyond",
        institutions=("QuSoft", "University of Amsterdam"),
        source_url="https://arxiv.org/abs/1806.01838",
        implementation="chronus.v33.memory.qsvt_from_block_enc",
        invariant="small block-encoded QSVT construction remains unitary",
        test_node="chronus/tests/test_chronus_v33/test_memory.py::test_qsvt_unitary",
    ),
)


PRODUCT_BOUNDARY_CASES: tuple[ResearchCase, ...] = (
    ResearchCase(
        key="vqc-clifford-gate-algebra",
        title="The Heisenberg representation of quantum computers",
        institutions=("Los Alamos National Laboratory",),
        source_url="https://arxiv.org/abs/quant-ph/9807006",
        implementation="turing_universal_quantum_computer.backends.reference.GATES",
        invariant=(
            "every gate in the published Clifford+T table is exactly unitary in "
            "Q(sqrt2) + i Q(sqrt2), checked by algebra and not by tolerance"
        ),
        test_node=(
            "turing_universal_quantum_computer/tests/test_backend_boundary.py"
            "::GatePropertyTests::test_every_gate_is_exactly_unitary"
        ),
    ),
    ResearchCase(
        key="vqc-clifford-t-exact-field",
        title="Exact synthesis of multiqubit Clifford+T circuits",
        institutions=("University of Waterloo", "Dalhousie University"),
        source_url="https://arxiv.org/abs/1212.0506",
        implementation="turing_universal_quantum_computer.backends.exact_algebra",
        invariant=(
            "after every gate of a mixed Clifford+T program the exact norm squared "
            "is still exactly 1 in the field, never a rounded float"
        ),
        test_node=(
            "turing_universal_quantum_computer/tests/test_backend_boundary.py"
            "::GatePropertyTests::test_normalisation_is_exact_after_every_gate"
        ),
    ),
    ResearchCase(
        key="vqc-stabilizer-full-width",
        title="Improved simulation of stabilizer circuits",
        institutions=("University of Texas at Austin", "University of Waterloo"),
        source_url="https://arxiv.org/abs/quant-ph/0406196",
        implementation="turing_universal_quantum_computer.backends.native.StabilizerBackend",
        invariant=(
            "a 10,000-qubit Clifford program reports a 20,000-bit tableau and one "
            "bit of cut entropy without materialising a single amplitude"
        ),
        test_node=(
            "turing_universal_quantum_computer/tests/test_backend_boundary.py"
            "::BackendParityTests::test_full_width_clifford_runs_without_materialising"
        ),
    ),
    ResearchCase(
        key="vqc-ghz-cut-entropy-parity",
        title="An introduction to entanglement measures",
        institutions=("Imperial College London", "University of Ulm"),
        source_url="https://arxiv.org/abs/quant-ph/0504163",
        implementation="turing_universal_quantum_computer.backends.execute",
        invariant=(
            "the single-qubit cut of a four-qubit GHZ state reports exactly one bit "
            "of entropy on the dense and the tableau backend alike"
        ),
        test_node=(
            "turing_universal_quantum_computer/tests/test_backend_boundary.py"
            "::BackendParityTests::test_ghz_entropy_agrees_across_backends"
        ),
    ),
    ResearchCase(
        key="vqc-bell-marginal-parity",
        title="Improved simulation of stabilizer circuits",
        institutions=("University of Texas at Austin", "University of Waterloo"),
        source_url="https://arxiv.org/abs/quant-ph/0406196",
        implementation="turing_universal_quantum_computer.backends.execute",
        invariant=(
            "a Bell marginal taken from the tableau equals the dense backend's exact "
            "marginal bitstring for bitstring, to the last digit"
        ),
        test_node=(
            "turing_universal_quantum_computer/tests/test_backend_boundary.py"
            "::BackendParityTests::test_bell_marginal_matches_dense_amplitudes"
        ),
    ),
    ResearchCase(
        key="vqc-no-undeclared-approximation",
        title="Quantum computing in the NISQ era and beyond",
        institutions=("California Institute of Technology",),
        source_url="https://arxiv.org/abs/1801.00862",
        implementation="turing_universal_quantum_computer.backends.execute",
        invariant=(
            "a program beyond the dense materialisation budget is answered by a "
            "narrower exact backend and never returns an approximate truth class"
        ),
        test_node=(
            "turing_universal_quantum_computer/tests/test_backend_boundary.py"
            "::RefusalBoundaryTests::test_no_execution_ever_returns_an_undeclared_approximation"
        ),
    ),
)


CASES: tuple[ResearchCase, ...] = ACADEMIC_CASES + PRODUCT_BOUNDARY_CASES


def validate_registry(cases: Iterable[ResearchCase] = CASES) -> None:
    seen: set[str] = set()
    for case in cases:
        if case.key in seen:
            raise ValueError(f"duplicate research key: {case.key}")
        seen.add(case.key)
        if not case.source_url.startswith("https://"):
            raise ValueError(f"non-HTTPS source for {case.key}")
        if "::" not in case.test_node or not case.invariant:
            raise ValueError(f"non-executable research case: {case.key}")
        if not (_REPO_ROOT / case.test_node.split("::", 1)[0]).is_file():
            raise ValueError(f"test node names a file outside this checkout: {case.test_node}")


__all__ = [
    "ACADEMIC_CASES",
    "CASES",
    "PRODUCT_BOUNDARY_CASES",
    "ResearchCase",
    "validate_registry",
]

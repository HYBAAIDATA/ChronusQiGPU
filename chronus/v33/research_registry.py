"""Executable, source-linked intake for quantum-computing methods.

A passing case means only that the named method-level invariant passes in this
repository.  It does not claim experimental replication, hardware advantage,
or validation of every conclusion in the cited publication.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


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


CASES: tuple[ResearchCase, ...] = (
    ResearchCase(
        key="qaoa-reference",
        title="A Quantum Approximate Optimization Algorithm",
        institutions=("MIT",),
        source_url="https://arxiv.org/abs/1411.4028",
        implementation="chronus.v33.academic.nist.NIST_Benchmark",
        invariant="p=1 two-vertex MaxCut QAOA cost reduction is positive",
        test_node="tests/test_chronus_v33/test_academic.py::test_nist_benchmark_determinism_score",
    ),
    ResearchCase(
        key="surface-code-single-error",
        title="Surface codes: Towards practical large-scale quantum computation",
        institutions=("University of California, Santa Barbara",),
        source_url="https://arxiv.org/abs/1208.0928",
        implementation="chronus.v33.academic.caltech.Caltech_Surface_Code",
        invariant="distance-3 reference decoder corrects a single injected Pauli error",
        test_node="tests/test_chronus_v33/test_academic.py::test_surface_code_decodes_single_error",
    ),
    ResearchCase(
        key="tensor-network-bell",
        title="Tensor-network quantum-circuit simulation",
        institutions=("University research implementations",),
        source_url="https://arxiv.org/abs/2310.03978",
        implementation="chronus.v33.academic.tensor_compression.MatrixProductState",
        invariant="Bell-state dense reconstruction and one-bit cut entropy agree",
        test_node="tests/test_chronus_v33/test_academic.py::test_mps_bell_state",
    ),
    ResearchCase(
        key="qsvt-unitarity",
        title="Quantum singular value transformation and beyond",
        institutions=("QuSoft", "University of Amsterdam"),
        source_url="https://arxiv.org/abs/1806.01838",
        implementation="chronus.v33.memory.qsvt_from_block_enc",
        invariant="small block-encoded QSVT construction remains unitary",
        test_node="tests/test_chronus_v33/test_memory.py::test_qsvt_unitary",
    ),
)


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


__all__ = ["CASES", "ResearchCase", "validate_registry"]

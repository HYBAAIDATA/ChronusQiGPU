from __future__ import annotations

from pathlib import Path

from chronus.v33.research_registry import (
    ACADEMIC_CASES,
    CASES,
    PRODUCT_BOUNDARY_CASES,
    validate_registry,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

_ACADEMIC_KEYS = {
    "qaoa-reference",
    "surface-code-single-error",
    "tensor-network-bell",
    "qsvt-unitarity",
}

_PRODUCT_BOUNDARY_KEYS = {
    "vqc-clifford-gate-algebra",
    "vqc-clifford-t-exact-field",
    "vqc-stabilizer-full-width",
    "vqc-ghz-cut-entropy-parity",
    "vqc-bell-marginal-parity",
    "vqc-no-undeclared-approximation",
}


def test_research_registry_is_source_linked_and_executable():
    validate_registry()
    assert {case.key for case in CASES} == _ACADEMIC_KEYS | _PRODUCT_BOUNDARY_KEYS


def test_every_registered_node_names_a_file_in_this_checkout():
    for case in CASES:
        path = case.test_node.split("::", 1)[0]
        assert (_REPO_ROOT / path).is_file(), case.key


def test_academic_cases_stay_inside_the_chronus_tree():
    assert len(ACADEMIC_CASES) == len(_ACADEMIC_KEYS)
    for case in ACADEMIC_CASES:
        assert case.implementation.startswith("chronus.v33.")
        assert case.as_dict()["command"].startswith("python -m pytest -q tests/")


def test_product_boundary_cases_address_the_vqc_package():
    assert len(PRODUCT_BOUNDARY_CASES) == len(_PRODUCT_BOUNDARY_KEYS)
    for case in PRODUCT_BOUNDARY_CASES:
        assert case.implementation.startswith("turing_universal_quantum_computer.")
        assert case.as_dict()["command"].startswith(
            "python -m pytest -q turing_universal_quantum_computer/tests/"
        )

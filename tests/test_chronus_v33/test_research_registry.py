from __future__ import annotations

from chronus.v33.research_registry import CASES, validate_registry


def test_research_registry_is_source_linked_and_executable():
    validate_registry()
    assert {case.key for case in CASES} == {
        "qaoa-reference",
        "surface-code-single-error",
        "tensor-network-bell",
        "qsvt-unitarity",
    }
    for case in CASES:
        row = case.as_dict()
        assert row["command"].startswith("python -m pytest -q tests/")
        assert case.implementation.startswith("chronus.v33.")

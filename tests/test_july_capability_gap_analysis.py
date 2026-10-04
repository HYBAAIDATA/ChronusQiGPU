"""Aggregate conformance gate for the preserved July 2026 capability inventory."""

from __future__ import annotations

import ast
import importlib
import io
import json
from pathlib import Path
import zipfile

import numpy as np
import pytest

from turing_universal_quantum_computer import (
    AlgorithmResult,
    EnhancedGroverAlgorithm,
    EnhancedQuantumFourierTransform,
    QuantumAccelerationEngine,
    UnsupportedAlgorithmError,
    redirect_historical_surface,
    run_all_verifications,
)
from kellogg.compressed_tensor import CompressionScheme, QuantumCompressedTensorEngine
from kellogg.tensor_serialization import (
    TensorSerializationError,
    load_pv,
    save_pv,
)
from turing_universal_quantum_computer.quantum_algorithms import VQE
from turing_universal_quantum_computer.trotter_simulation import TrotterHamiltonianSimulator


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "manifests" / "july_2026_capability_gap_analysis.json"
ACTIVE_STATUSES = {"present", "elevated", "adapter-added"}
ALLOWED_STATUSES = ACTIVE_STATUSES | {"superseded", "retired-with-reason"}


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _test_definitions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
    return names


def _resolve_redirect(target: str) -> None:
    if "/" in target:
        module_name, names = target.rsplit(".", 1)
        module = importlib.import_module(module_name)
        for name in names.split("/"):
            assert getattr(module, name) is not None
        return
    for symbol in (target,):
        parts = symbol.split(".")
        for boundary in range(len(parts), 0, -1):
            try:
                resolved = importlib.import_module(".".join(parts[:boundary]))
            except ImportError:
                continue
            for attribute in parts[boundary:]:
                resolved = getattr(resolved, attribute)
            assert resolved is not None
            break
        else:
            raise AssertionError(f"redirect target is not importable: {symbol}")


def test_gap_manifest_has_stable_schema_and_complete_inventory():
    raw = MANIFEST_PATH.read_text(encoding="utf-8")
    manifest = json.loads(raw)
    assert set(manifest) == {"schema", "reference_date", "source_artifacts", "entries"}
    assert manifest["schema"] == "pythia.july-2026-capability-gap-analysis/v1"
    assert manifest["reference_date"] == "2026-07-24"
    assert raw == json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    assert len(manifest["source_artifacts"]) == 4
    assert len(manifest["entries"]) >= 20
    ids = [entry["id"] for entry in manifest["entries"]]
    assert len(ids) == len(set(ids))
    for entry in manifest["entries"]:
        assert set(entry) == {
            "id",
            "source_module",
            "public_surface",
            "historical_capability",
            "current_owner",
            "current_path",
            "status",
            "symbol",
            "evidence_tests",
            "claim_boundary",
            "redirect",
            "retirement_reason",
        }
        assert entry["status"] in ALLOWED_STATUSES
        assert entry["historical_capability"]
        assert entry["current_owner"]
        assert entry["current_path"]
        assert entry["claim_boundary"]
        assert entry["evidence_tests"]
        if entry["status"] in ACTIVE_STATUSES:
            assert entry["symbol"]
            assert {evidence["kind"] for evidence in entry["evidence_tests"]} == {
                "unit",
                "invariant",
                "integration",
            }
        else:
            assert entry["redirect"]
            assert entry["retirement_reason"]


def test_aggregate_active_capability_gate_imports_symbols_and_named_evidence():
    """Every active manifest row must resolve to code and all three test classes."""
    for entry in _manifest()["entries"]:
        if entry["status"] not in ACTIVE_STATUSES:
            continue
        module_name, symbol_name = entry["symbol"].split(":", 1)
        assert getattr(importlib.import_module(module_name), symbol_name) is not None, entry["id"]
        for evidence in entry["evidence_tests"]:
            relative, test_name = evidence["nodeid"].split("::", 1)
            test_path = ROOT / relative
            assert test_path.is_file(), (entry["id"], evidence["nodeid"])
            assert test_name.split("::")[-1] in _test_definitions(test_path), (
                entry["id"],
                evidence["nodeid"],
            )


def test_retired_surfaces_have_executable_redirects():
    from turing_universal_quantum_computer.july_compat import HISTORICAL_REDIRECTS

    entries = {
        surface.strip(): entry
        for entry in _manifest()["entries"]
        if entry["status"] in {"superseded", "retired-with-reason"}
        for surface in entry["public_surface"].split(",")
    }
    for name, redirect in HISTORICAL_REDIRECTS.items():
        assert name in entries
        assert entries[name]["redirect"] == redirect
        assert redirect_historical_surface(name) == redirect
        _resolve_redirect(redirect)
    assert all(entry["retirement_reason"] for entry in entries.values())


def test_algorithm_adapters_are_bounded_and_make_no_hardware_or_speedup_claim():
    grover = EnhancedGroverAlgorithm().run(2, [3], iterations=1)
    assert grover.result["peak_success_probability"] == pytest.approx(1.0)
    assert grover.speedup_claim is False
    assert grover.physical_hardware is False
    assert grover.consensus_authority is False
    with pytest.raises(ValueError, match="cannot assert"):
        AlgorithmResult(
            "grover",
            "fake",
            "finite_precision_software_simulation",
            {},
            speedup_claim=True,
        )

    qft = EnhancedQuantumFourierTransform().transform(2)
    assert (qft.result.rows, qft.result.cols) == (4, 4)
    assert qft.speedup_claim is False
    with pytest.raises(ValueError, match="unique"):
        QuantumAccelerationEngine().run_grover(2, [1, 1])
    with pytest.raises(ValueError, match="outside"):
        QuantumAccelerationEngine().run_grover(2, [4])
    with pytest.raises(TypeError, match="integers"):
        QuantumAccelerationEngine().run_grover(2, [True])
    with pytest.raises(ValueError, match="non-negative"):
        QuantumAccelerationEngine().run_grover(2, [1], iterations=-1)
    with pytest.raises(UnsupportedAlgorithmError, match="bounded dense adapter"):
        QuantumAccelerationEngine(max_qubits=1).run_qft(2)
    with pytest.raises(UnsupportedAlgorithmError, match="no validated implementation"):
        QuantumAccelerationEngine().run_shor(15)


def test_algorithm_result_rejects_overclaim():
    with pytest.raises(ValueError, match="cannot assert"):
        AlgorithmResult(
            "grover",
            "untrusted",
            "finite_precision_software_simulation",
            {},
            speedup_claim=True,
        )


def test_algorithm_result_keeps_claim_flags_false():
    result = EnhancedGroverAlgorithm().run(2, [3], iterations=1)
    assert (result.speedup_claim, result.physical_hardware, result.consensus_authority) == (
        False,
        False,
        False,
    )


def test_enhanced_grover_and_qft_integrate_with_canonical_algorithms():
    grover = EnhancedGroverAlgorithm().run(2, [3], iterations=1)
    qft = EnhancedQuantumFourierTransform().transform(2)
    assert grover.result["peak_success_probability"] == pytest.approx(1.0)
    assert (qft.result.rows, qft.result.cols) == (4, 4)


def test_algorithm_adapter_rejects_invalid_domains_and_types():
    engine = QuantumAccelerationEngine(max_qubits=1)
    with pytest.raises(ValueError, match="unique"):
        engine.run_grover(1, [0, 0])
    with pytest.raises(ValueError, match="outside"):
        engine.run_grover(1, [2])
    with pytest.raises(TypeError, match="integers"):
        engine.run_grover(1, [True])
    with pytest.raises(ValueError, match="non-negative"):
        engine.run_grover(1, [1], iterations=-1)
    with pytest.raises(UnsupportedAlgorithmError, match="bounded dense adapter"):
        engine.run_qft(2)
    with pytest.raises(TypeError, match="boolean"):
        QuantumAccelerationEngine().run_qft(1, inverse=1)


def test_operator_verification_report_returns_canonical_report():
    report = run_all_verifications()
    assert report.total_passed == len(report.results)


def test_operator_verification_report_covers_core_invariants():
    report = run_all_verifications()
    invariant_names = {result.invariant_type.value for result in report.results}
    assert {"cptp_map", "unitarity", "hermiticity", "positive_semidefiniteness"} <= (
        invariant_names
    )


def test_operator_verification_report_fails_closed():
    with pytest.raises(AssertionError, match="invariant suite failed"):
        run_all_verifications(op=lambda value: value + 1, inv_op=lambda value: value)


def test_trotter_adapter_rejects_non_hermitian_hamiltonians():
    with pytest.raises(ValueError, match="Hermitian"):
        TrotterHamiltonianSimulator(1, np.array([[0.0, 1.0], [0.0, 0.0]]))


def test_current_vqe_surface_executes_finite_bounded_problem():
    hamiltonian = VQE.ising_hamiltonian()
    result = VQE().optimize(hamiltonian, [0.1, 0.2, 0.3, 0.4], iterations=2)
    assert len(result["history"]) == 2
    assert np.isfinite(result["final_energy"])


def test_vqe_hamiltonian_is_hermitian():
    matrix = VQE.ising_hamiltonian()
    for row in range(matrix.rows):
        for column in range(matrix.cols):
            assert matrix.data[row][column] == matrix.data[column][row].conj()


def test_vqe_result_respects_variational_energy_bound():
    result = VQE().optimize(
        VQE.ising_hamiltonian(), [0.1, 0.2, 0.3, 0.4], iterations=2
    )
    assert result["final_energy"] >= result["exact_ground_energy"] - 1e-10


def test_malformed_pv_payload_is_rejected(tmp_path):
    engine = QuantumCompressedTensorEngine()
    tensor = engine.load_tensor_from_host(
        np.arange(4.0), scheme=CompressionScheme.NONE
    )
    path = tmp_path / "tensor.pv"
    save_pv(path, tensor, b"test-key")
    with zipfile.ZipFile(path) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    members["arrays/0.npy"] = members["arrays/0.npy"] + b"corruption"
    malformed = tmp_path / "malformed.pv"
    with zipfile.ZipFile(malformed, "w") as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)
    with pytest.raises(TensorSerializationError):
        load_pv(malformed, b"test-key")
    invalid = tmp_path / "invalid.pv"
    invalid.write_bytes(b"not a zip artifact")
    with pytest.raises(TensorSerializationError):
        load_pv(invalid)

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from python_backend.core_modules.geodesic_tensor_engine import fold_exact
from python_backend.core_modules.math_folding import PHI as EXACT_PHI
from python_backend.core_modules.math_folding import Quadratic5, pulvini_fold
from quantum_compute_substrate import pulvini as pulvini_pkg
from quantum_compute_substrate.pulvini import (
    PHI,
    PulviniDataOrchestrator,
    PulviniOperator,
    PythagorasOrchestrator,
)
from scripts.check_pulvini_data_boundary import check_repository


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_exact_phi_satisfies_defining_quadratic_identity() -> None:
    one = Quadratic5(Fraction(1), Fraction(0))
    assert EXACT_PHI * EXACT_PHI == EXACT_PHI + one


def test_phi_is_structural_in_fold_not_decorative_metadata() -> None:
    operator = PulviniOperator()
    x = np.array([2.0, 3.0, 5.0, 7.0])
    folded, kernel = operator.fold(x)

    dim_n1, dim_n2 = operator._get_fibonacci_split(len(x))
    left = x[:dim_n1]
    right = x[dim_n1:]
    right_padded = np.zeros(dim_n1)
    right_padded[:dim_n2] = right

    w1 = 1.0 / PHI
    w2 = 1.0 / (PHI**2)
    expected_folded = w1 * left + w2 * right_padded
    expected_kernel = w2 * left - w1 * right_padded

    assert np.allclose(folded, expected_folded)
    assert np.allclose(kernel, expected_kernel)

    fake_phi = 2.0
    fake_folded = (1.0 / fake_phi) * left + (1.0 / (fake_phi**2)) * right_padded
    assert not np.allclose(folded, fake_folded)

    recovered = operator.unfold(folded, kernel, len(x))
    assert np.allclose(recovered, x, atol=1e-12)


def test_exact_pulvini_pair_fold_never_truncates() -> None:
    source = tuple(Fraction(v) for v in (1, 1, 2, 3, 5, 8, 13))
    folded = pulvini_fold(source)
    assert folded.original_length == len(source)
    assert folded.unfold() == source


def test_exact_geodesic_fold_roundtrip_preserves_full_state() -> None:
    source = tuple(range(17))
    state = fold_exact(source, depth=4)
    assert state.original_length == len(source)
    assert tuple(int(v) for v in state.unfold()) == source
    assert state.verify_content_hash() is True


def test_canonical_router_is_data_authority_not_mining() -> None:
    router = PulviniDataOrchestrator(data_threshold=100)
    result = router.solve(np.arange(32.0))

    assert result["authority"] == "pulvini.data"
    assert result["domain"] == "data"
    assert result["mining_path"] is False
    assert result["data_threshold"] == 100


def test_pythagoras_compatibility_is_deprecated_read_only_and_non_authoritative() -> None:
    assert pulvini_pkg.PulviniDataOrchestrator is PulviniDataOrchestrator
    assert PythagorasOrchestrator is not PulviniDataOrchestrator

    with pytest.warns(DeprecationWarning, match="historical compatibility"):
        legacy = PythagorasOrchestrator(quantum_threshold=100)
    result = legacy.solve(np.arange(32.0))

    assert result["authority"] == "pulvini.data"
    assert result["domain"] == "data"
    assert result["mining_path"] is False
    assert result["compatibility_alias"] == "PythagorasOrchestrator"
    with pytest.raises(AttributeError, match="read-only compatibility"):
        legacy.data_threshold = 1


def test_repository_pulvini_data_boundary_gate_passes() -> None:
    assert check_repository(REPO_ROOT) == []


def test_boundary_gate_rejects_mining_import_of_pulvini(tmp_path: Path) -> None:
    source = tmp_path / "mining" / "bad_route.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from quantum_compute_substrate.pulvini import PulviniDataOrchestrator\n",
        encoding="utf-8",
    )
    violations = check_repository(tmp_path)
    assert any(v.rule == "mining-imports-pulvini-data" for v in violations)


def test_boundary_gate_rejects_dynamic_mining_import_of_pulvini(tmp_path: Path) -> None:
    source = tmp_path / "chronus" / "v99" / "mining" / "dynamic_route.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "import importlib\n"
        "P = importlib.import_module('quantum_compute_substrate.pulvini')\n",
        encoding="utf-8",
    )
    violations = check_repository(tmp_path)
    assert any(v.rule == "mining-imports-pulvini-data" for v in violations)


def test_boundary_gate_rejects_pulvini_import_of_mining(tmp_path: Path) -> None:
    source = tmp_path / "quantum_compute_substrate" / "pulvini" / "bad_operator.py"
    source.parent.mkdir(parents=True)
    source.write_text("from mining.hash_pipeline import grind\n", encoding="utf-8")
    violations = check_repository(tmp_path)
    assert any(v.rule == "pulvini-imports-mining" for v in violations)


def test_boundary_gate_rejects_active_historical_path_caller(tmp_path: Path) -> None:
    source = tmp_path / "Intelligence" / "bad_historical_import.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from python_backend.hyba_data.quantum_honest import grover_cost\n",
        encoding="utf-8",
    )
    violations = check_repository(tmp_path)
    assert any(
        v.rule == "active-caller-of-absent-historical-path" for v in violations
    )


def test_boundary_gate_rejects_production_pythagoras_compatibility_use(
    tmp_path: Path,
) -> None:
    source = tmp_path / "euclid" / "bad_authority.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from quantum_compute_substrate.pulvini import PythagorasOrchestrator\n"
        "router = PythagorasOrchestrator()\n",
        encoding="utf-8",
    )
    violations = check_repository(tmp_path)
    assert any(
        v.rule == "production-uses-pythagoras-compatibility" for v in violations
    )


def test_pulvini_public_api_exposes_no_mining_authority() -> None:
    exported = {str(name).lower() for name in pulvini_pkg.__all__}
    forbidden = {"nonce", "stratum", "share", "pool", "sha256d", "miner", "mining"}
    assert not any(any(token in name for token in forbidden) for name in exported)

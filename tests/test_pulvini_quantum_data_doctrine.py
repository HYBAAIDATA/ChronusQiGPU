from __future__ import annotations

import ast
from fractions import Fraction
from pathlib import Path

import numpy as np

from python_backend.core_modules.geodesic_tensor_engine import fold_exact
from python_backend.core_modules.math_folding import PHI as EXACT_PHI
from python_backend.core_modules.math_folding import Quadratic5, pulvini_fold
from quantum_compute_substrate import pulvini as pulvini_pkg
from quantum_compute_substrate.pulvini import PHI, PulviniDataOrchestrator, PulviniOperator


REPO_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_PULVINI_ROOT = REPO_ROOT / "quantum_compute_substrate" / "pulvini"


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

    # Ablation: replacing phi by an arbitrary value changes the transform.
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


def test_pythagoras_name_is_compatibility_only() -> None:
    assert pulvini_pkg.PythagorasOrchestrator is PulviniDataOrchestrator
    assert pulvini_pkg.PulviniDataOrchestrator is PulviniDataOrchestrator


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_active_pulvini_package_has_no_mining_imports() -> None:
    forbidden_fragments = (
        "pythia_mining",
        "mining.stratum",
        "mining.hash_pipeline",
        "mining.production_miner",
        "stratum_client",
    )
    scanned = list(ACTIVE_PULVINI_ROOT.glob("*.py"))
    scanned += [
        REPO_ROOT / "tensor" / "pulvini_bridge.py",
        REPO_ROOT / "python_backend" / "core_modules" / "math_folding.py",
        REPO_ROOT / "python_backend" / "core_modules" / "geodesic_tensor_engine.py",
    ]
    violations: list[tuple[str, str]] = []
    for path in scanned:
        for module in _imports(path):
            if any(fragment in module for fragment in forbidden_fragments):
                violations.append((str(path.relative_to(REPO_ROOT)), module))
    assert violations == []


def test_pulvini_public_api_exposes_no_mining_authority() -> None:
    exported = {str(name).lower() for name in pulvini_pkg.__all__}
    forbidden = {"nonce", "stratum", "share", "pool", "sha256d", "miner", "mining"}
    assert not any(any(token in name for token in forbidden) for name in exported)

from __future__ import annotations

from pathlib import Path

from scripts.check_pulvini_data_boundary import check_repository


def _write(root: Path, relative: str, source: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_pulvini_cannot_import_canonical_chronus_mining_coordinator(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "quantum_compute_substrate/pulvini/bad_mining_edge.py",
        "from chronus.mla1517.mining.coordinator import IntelligentPoolCoordinator\n",
    )

    violations = check_repository(tmp_path)

    assert any(
        violation.rule == "pulvini-imports-mining"
        and "chronus.mla1517.mining.coordinator" in violation.detail
        for violation in violations
    )


def test_platform_manifold_pool_coordinator_cannot_import_pulvini(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "chronus/mla1517_platform/python/manifold_pool_coordinator.py",
        "from quantum_compute_substrate.pulvini import PulviniDataOrchestrator\n",
    )

    violations = check_repository(tmp_path)

    assert any(
        violation.rule == "mining-imports-pulvini-data"
        and violation.path.endswith("manifold_pool_coordinator.py")
        for violation in violations
    )


def test_platform_canonical_coordinator_cannot_import_pulvini(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "chronus/mla1517_platform/python/coordinator.py",
        "from quantum_compute_substrate.pulvini import PulviniDataOrchestrator\n",
    )

    violations = check_repository(tmp_path)

    assert any(
        violation.rule == "mining-imports-pulvini-data"
        and violation.path.endswith("coordinator.py")
        for violation in violations
    )


def test_production_transport_remains_classified_as_mining(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "chronus/mla1517/mining/production_transport.py",
        "from quantum_compute_substrate.pulvini import PulviniDataOrchestrator\n",
    )

    violations = check_repository(tmp_path)

    assert any(
        violation.rule == "mining-imports-pulvini-data"
        and violation.path.endswith("production_transport.py")
        for violation in violations
    )

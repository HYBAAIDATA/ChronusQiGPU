from __future__ import annotations

from chronus.virtual_igpu import ProductMode, execution_policy_for_product_mode
from chronus.readiness import (
    ACCELERATOR_MODE,
    CORE_MODE,
    AcceleratorCertification,
    CoreProductionEvidence,
    EvidenceRef,
    audit_core_surfaces,
    production_readiness,
)


def _ref(kind: str, subject: str) -> EvidenceRef:
    return EvidenceRef(
        kind=kind,
        artifact_sha256="a" * 64,
        observed_at="2026-10-07T00:00:00+00:00",
        subject=subject,
        producer="local-production-readiness-run",
        metadata={"git_head": "b" * 40},
    )


def _core_evidence() -> CoreProductionEvidence:
    return CoreProductionEvidence(
        software_execution=_ref(
            "chronus_software_execution", "standalone software execution"
        ),
        independent_verification=_ref(
            "chronus_independent_verification", "independent result verification"
        ),
        receipt_identity=_ref(
            "chronus_receipt_identity", "receipt identity binding"
        ),
        custody_restart=_ref(
            "chronus_custody_restart", "THESEUS fresh-process restart"
        ),
        clean_install=_ref(
            "chronus_clean_install", "clean wheel install and execution"
        ),
        full_suite=_ref(
            "chronus_full_suite", "current-head complete software suite"
        ),
    )


def test_owner_approved_core_surfaces_are_importable() -> None:
    gates = audit_core_surfaces()
    assert gates
    assert all(gate.passed for gate in gates)


def test_native_chronus_gpu_can_be_ready_without_any_host_gpu_certification() -> None:
    report = production_readiness(_core_evidence())

    assert report["production_ready"] is True
    assert report["core_production_ready"] is True
    assert CORE_MODE in report["ready_modes"]
    assert report["modes"][CORE_MODE]["requires_physical_gpu"] is False

    assert ACCELERATOR_MODE not in report["ready_modes"]
    assert report["modes"][ACCELERATOR_MODE]["ready"] is False
    assert report["modes"][ACCELERATOR_MODE]["requires_physical_gpu"] is True


def test_missing_core_evidence_never_becomes_ready_because_gpu_exists() -> None:
    cert = AcceleratorCertification(
        backend="metal",
        device_id="apple:m3",
        artifact_sha256="c" * 64,
        observed_at="2026-10-07T00:00:00+00:00",
        subject="M3 device-bound run",
        producer="device-certifier",
        execution_observed=True,
        correctness_verified=True,
    )

    report = production_readiness(
        CoreProductionEvidence(),
        accelerator_certifications=[cert],
    )

    assert report["core_production_ready"] is False
    assert report["production_ready"] is False
    assert report["modes"][ACCELERATOR_MODE]["ready"] is False


def test_certified_accelerator_is_additive_to_ready_core() -> None:
    cert = AcceleratorCertification(
        backend="metal",
        device_id="apple:m3",
        artifact_sha256="c" * 64,
        observed_at="2026-10-07T00:00:00+00:00",
        subject="M3 device-bound run",
        producer="device-certifier",
        execution_observed=True,
        correctness_verified=True,
    )

    report = production_readiness(
        _core_evidence(),
        accelerator_certifications=[cert],
    )

    assert set(report["ready_modes"]) == {CORE_MODE, ACCELERATOR_MODE}
    lane = report["modes"][ACCELERATOR_MODE]["lanes"][0]
    assert lane["ready"] is True
    assert lane["backend"] == "metal"
    assert lane["device_id"] == "apple:m3"


def test_uncertified_accelerator_never_demotes_native_chronus_gpu() -> None:
    cert = AcceleratorCertification(
        backend="opencl",
        device_id="unknown",
        artifact_sha256="d" * 64,
        observed_at="2026-10-07T00:00:00+00:00",
        subject="probe only",
        producer="device-probe",
        execution_observed=False,
        correctness_verified=False,
    )

    report = production_readiness(
        _core_evidence(),
        accelerator_certifications=[cert],
    )

    assert report["core_production_ready"] is True
    assert report["modes"][CORE_MODE]["ready"] is True
    assert report["modes"][ACCELERATOR_MODE]["ready"] is False
    assert "physical execution was not observed" in (
        report["modes"][ACCELERATOR_MODE]["lanes"][0]["detail"]
    )


def test_convergence_manifest_pins_original_two_mode_design() -> None:
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    manifest = json.loads(
        (root / "chronus" / "CONVERGENCE_MANIFEST.json").read_text(encoding="utf-8")
    )

    native = manifest["product_modes"]["native_chronus_gpu"]
    augmented = manifest["product_modes"]["host_gpu_augmentation"]

    assert manifest["schema"] == "chronus.convergence-manifest/v2"
    assert native["physical_gpu_required"] is False
    assert native["status"] == "implemented"
    assert native["policy"] == "standalone_software"
    assert augmented["physical_gpu_required"] is True
    assert augmented["policy"] == "preferred_accelerator"
    assert "physical GPU required for CHRONUS core availability" in manifest[
        "prohibited_regressions"
    ]
    assert manifest["capabilities"]["m32_manifold_and_qsdl"]["status"] == "implemented"
    assert manifest["capabilities"]["lucas_pisot_scale_contract"]["status"] == "implemented"
    assert manifest["capabilities"]["pythia_mining_execution"]["status"] == "implemented"


def test_product_mode_is_not_backend_identity() -> None:
    assert ProductMode.NATIVE_CHRONUS_GPU.value == CORE_MODE
    assert ProductMode.HOST_GPU_AUGMENTATION.value == ACCELERATOR_MODE
    assert (
        execution_policy_for_product_mode(ProductMode.NATIVE_CHRONUS_GPU)
        == "standalone_software"
    )
    assert (
        execution_policy_for_product_mode(ProductMode.HOST_GPU_AUGMENTATION)
        == "preferred_accelerator"
    )


def test_core_readiness_does_not_require_cpu_or_gpu_adapter_identity() -> None:
    gates = {gate.name: gate for gate in audit_core_surfaces()}
    assert gates["virtual_igpu"].passed is True
    assert "ProductMode" in gates["virtual_igpu"].detail
    assert "CPUEmulatorAdapter" not in gates["virtual_igpu"].detail

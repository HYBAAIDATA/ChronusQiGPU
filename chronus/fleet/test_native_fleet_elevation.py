"""End-to-End Qualification Suite for Chronus Native Quantum Fleet Elevation (Sections 0–7)."""

from __future__ import annotations

import hashlib
from pathlib import Path
import pytest

import chronus
from chronus.fleet import (
    IMMUTABLE_GOVERNANCE_SURFACES,
    ORDERED_PROMOTION_STAGES,
    PRODUCT_AUTHORITIES,
    AdmissionController,
    AdmissionDecisionStatus,
    AuthorityGrant,
    BlindRetryForbiddenError,
    CapacitySnapshot,
    CohortBoundaryGuard,
    CohortKind,
    ContentAddressedMathCache,
    DurableMutationLatch,
    ImmutablePlanRegistry,
    LatchState,
    PromotionGateController,
    PromotionStage,
    ReferenceFleetAllocation,
    ResourceVector,
    StageTelemetryEvidence,
    StructuredOperatorWorkspace,
    TenantBudgetQuota,
    build_gpu_reference_comparison_panel,
    canonical_workload_fixtures,
    capture_host_environment,
    compute_quantiles,
    default_cohort_registry,
    evaluate_native_elevation,
    run_all_workload_fixtures,
    run_benchmark_suite,
    run_recovery_and_security_proofs,
    verify_optimized_python_parity,
)
from chronus.gpu_reference import GPU_REFERENCE_2026, get_gpu_spec


def test_section0_baseline_contract_and_gpu_reference_panel() -> None:
    contract_doc = Path(__file__).resolve().parents[2] / "docs" / "NATIVE_QUANTUM_CONTRACT.md"
    assert contract_doc.is_file()
    text = contract_doc.read_text(encoding="utf-8")
    assert "ONE iGPU" in text
    assert "Quantum Content Comes From Mathematics" in text

    required_keys = {"rubin_r100", "blackwell_ultra_b300", "amd_mi355x", "amd_mi325x", "hopper_h100"}
    assert required_keys <= set(GPU_REFERENCE_2026)
    assert get_gpu_spec("hgx_b300").name.startswith("NVIDIA Blackwell Ultra")
    assert get_gpu_spec("mi355x").manufacturer == "AMD"
    assert get_gpu_spec("mi325x").memory_capacity_gb == 256
    assert hasattr(chronus, "ReferenceFleetAllocation")
    assert hasattr(chronus, "PromotionGateController")


def test_section1_workload_contracts_a_through_e() -> None:
    fixtures = canonical_workload_fixtures()
    assert set(fixtures) == {
        "fixture_a_exact_algebraic_quantum",
        "fixture_a_exact_domain_refusal",
        "fixture_b_native_quantum_numerical",
        "fixture_c_tensor_kellogg_planes",
        "fixture_d_resident_data_ovid_theseus",
        "fixture_e_integrated_service_lifecycle",
    }
    suite = run_all_workload_fixtures()
    assert suite["all_verified"] is True
    assert suite["fixture_count"] == 6
    assert suite["outcomes"]["fixture_a_exact_domain_refusal"]["actual_outcome"] == "refusal"
    assert suite["outcomes"]["fixture_e_integrated_service_lifecycle"]["verified"] is True


def test_section2_benchmark_harness_100_observations_and_opt_parity() -> None:
    env = capture_host_environment()
    assert env.logical_cpus >= 1
    assert env.acceptance_classification in {"source_component_study", "installed_acceptance"}

    q = compute_quantiles([1.0, 2.0, 3.0, 4.0, 5.0, 10.0], method="weibull")
    assert q.min_ms <= q.p50_ms <= q.p90_ms <= q.p95_ms <= q.p99_ms <= q.max_ms

    suite = run_benchmark_suite(
        observations_per_case=100,
        seed=20261024,
        quantile_method="weibull",
    )
    assert suite["comparative_study_qualified"] is True
    for cid, case_data in suite["cases"].items():
        assert case_data["observations"] == 100
        assert case_data["comparative_study_eligible"] is True
        assert case_data["failed_count"] == 0
        assert case_data["all_verified"] is True
        assert len(case_data["raw_kernel_samples_ms"]) == 100
        assert len(case_data["raw_end_to_end_samples_ms"]) == 100
        if cid == "case_a_domain_refusal":
            assert case_data["refused_count"] == 100
        else:
            assert case_data["succeeded_count"] == 100

    panel = build_gpu_reference_comparison_panel()
    assert panel["native_chronus_lane"]["physical_gpu_required"] is False
    assert panel["native_chronus_lane"]["fictional_tflops_or_hbm_claimed"] is False
    for dev in panel["vendor_reference_devices"]:
        assert dev["live_competitor_execution_status"] == "NOT_RUN"
        assert dev["native_blocker"] is False
        assert dev["fictional_gpu_equivalence_claimed"] is False

    parity = verify_optimized_python_parity()
    assert parity["passed"] is True
    assert parity["sub_payload"]["debug_enabled"] is False


def test_section3_native_elevation_and_cache_safety() -> None:
    cache = ContentAddressedMathCache(max_entries=16)
    with pytest.raises(PermissionError):
        cache.get_or_compute(
            operation="authorization_grant",
            input_payload={"user": "alice"},
            precision_plane="exact",
            compute_fn=lambda: {"granted": True},
        )
    with pytest.raises(PermissionError):
        cache.get_or_compute(
            operation="tenant_quota_check",
            input_payload={"tenant": "t1"},
            precision_plane="exact",
            compute_fn=lambda: {"ok": True},
        )

    reg = ImmutablePlanRegistry(max_plans=16)
    m1 = reg.get_manifest(32, 4, "standalone", "cpu_reference")
    m2 = reg.get_manifest(32, 4, "standalone", "cpu_reference")
    assert m1 == m2
    assert reg.hits == 1

    ws = StructuredOperatorWorkspace([0.5, 0.5, 0.5, 0.5], 1.618033988749895)
    out = ws.matvec_into([1.0 + 0j, 0.0 + 1j, -1.0 + 0j, 0.0 - 1j])
    assert out.shape == (4,)

    elev = evaluate_native_elevation(observations=100)
    assert elev["exact_and_float_planes_separated"] is True
    assert elev["error_bound_widened"] is False
    assert elev["fictional_speedup_claimed"] is False
    assert elev["max_numerical_drift_vs_baseline"] <= 1e-15
    assert elev["math_cache_stats"]["hits"] > 0


def test_section4_isolated_cohorts_and_120_slot_fleet_model() -> None:
    cohorts = default_cohort_registry()
    assert set(cohorts) == {
        CohortKind.VERIFIER,
        CohortKind.BENCHMARK,
        CohortKind.SHADOW,
        CohortKind.CANARY,
        CohortKind.PRODUCTION,
    }
    shadow = cohorts[CohortKind.SHADOW]
    assert shadow.can_mutate_production_custody is False

    # Valid candidate schedule proposal succeeds as non-promoted proposal
    prop = CohortBoundaryGuard.validate_proposal(
        proposer_cohort=shadow,
        target_surface="candidate_schedule",
        proposed_changes={"lanes": 8},
    )
    assert prop["admissible_as_candidate_proposal"] is True
    assert prop["auto_promoted_to_production"] is False

    # Attempt to mutate protected governance surfaces fails closed
    for surface in IMMUTABLE_GOVERNANCE_SURFACES:
        with pytest.raises(PermissionError):
            CohortBoundaryGuard.validate_proposal(
                proposer_cohort=shadow,
                target_surface=surface,
                proposed_changes={"override": True},
            )

    alloc = ReferenceFleetAllocation()
    assert alloc.total_modeled_slots == 120
    assert alloc.production_commitment_slots == 60
    assert alloc.protected_recovery_reserve_slots == 48
    assert alloc.isolated_elevation_slots == 6
    assert alloc.worker_local_control_slots == 6
    assert alloc.mining_default_slots == 0
    assert alloc.implicit_live_pool_authority is False
    assert alloc.recovery_reserve_sold_as_idle is False
    assert alloc.deployed_hardware_inventory_claimed is False
    assert alloc.availability_certificate_claimed is False

    domains = alloc.domain_layouts()
    assert len(domains) == 3
    for d in domains:
        assert d.total_domain_slots == 40
        assert (
            d.production_slots,
            d.recovery_reserve_slots,
            d.elevation_preemptible_slots,
            d.local_control_verification_slots,
        ) == (20, 16, 2, 2)

    loss = alloc.simulate_domain_loss(lost_domains=1)
    assert loss["surviving_modeled_slots"] == 80
    assert loss["production_slots_maintained"] == 60
    assert loss["surviving_local_control_slots"] == 4
    assert loss["optional_elevation_slots_active"] == 4
    assert loss["total_used_slots"] == 68
    assert loss["unallocated_headroom_slots"] == 12
    assert loss["production_commitments_fully_preserved"] is True


def test_section5_authority_and_resource_vector_admission(tmp_path: Path) -> None:
    expected_authorities = {
        "Chronus",
        "Kellogg",
        "TURING",
        "TOE",
        "EUCLID",
        "AL HARAS",
        "THESEUS",
        "OVID",
        "Salamander",
        "Hermitten",
    }
    assert set(PRODUCT_AUTHORITIES) == expected_authorities

    key = b"al-haras-unit-test-signing-key-32b"
    ctrl = AdmissionController(audit_dir=tmp_path / "audit", signing_key=key)
    ctrl.register_tenant(TenantBudgetQuota(tenant_id="tenant_1"))
    cap = ctrl.default_capacity_snapshot(now_ms=1000)

    rv = ResourceVector(
        cpu_time_ms=500,
        peak_memory_bytes=16 * 1024 * 1024,
        custody_bytes=4096,
        custody_io_bps=1024 * 1024,
        network_bytes=0,
        deadline_epoch_ms=10_000,
        exactness_plane="exact",
        verification_required=True,
        tenant_id="tenant_1",
        workload_class="exact_quantum",
    )

    grant = AuthorityGrant.issue(
        signing_key=key,
        grant_id="g1",
        tenant_id="tenant_1",
        workload_id="w1",
        owner_authority="TURING",
        resource_vector=rv,
        nonce="nonce_1",
        issued_at_ms=1000,
    )
    receipt = ctrl.admit_and_execute(
        grant=grant,
        resource_vector=rv,
        workload_id="w1",
        owner_authority="TURING",
        capacity=cap,
        mutation_fn=lambda: {"lucas_15": 1364},
        postcondition_fn=lambda r: r.get("lucas_15") == 1364,
        now_ms=1100,
    )
    assert receipt.status == AdmissionDecisionStatus.ADMITTED
    assert receipt.postcondition_verified is True
    assert receipt.pre_mutation_audit_digest is not None

    # Replay with same nonce is refused fail-closed
    replay_rec = ctrl.admit_and_execute(
        grant=grant,
        resource_vector=rv,
        workload_id="w1",
        owner_authority="TURING",
        capacity=cap,
        mutation_fn=lambda: {"lucas_15": 1364},
        postcondition_fn=lambda r: True,
        now_ms=1200,
    )
    assert replay_rec.status == AdmissionDecisionStatus.REFUSED
    assert replay_rec.reason == "replayed_authority_grant_nonce"

    # Stale capacity is deferred fail-closed
    grant2 = AuthorityGrant.issue(
        signing_key=key,
        grant_id="g2",
        tenant_id="tenant_1",
        workload_id="w2",
        owner_authority="TURING",
        resource_vector=rv,
        nonce="nonce_2",
        issued_at_ms=1000,
    )
    stale_cap = CapacitySnapshot(
        captured_at_ms=1000,
        known=True,
        available_slots_by_class={"exact_quantum": 12},
    )
    stale_rec = ctrl.admit_and_execute(
        grant=grant2,
        resource_vector=rv,
        workload_id="w2",
        owner_authority="TURING",
        capacity=stale_cap,
        mutation_fn=lambda: {"ok": True},
        postcondition_fn=lambda _: True,
        now_ms=50_000,  # > 30_000 ms staleness limit
    )
    assert stale_rec.status == AdmissionDecisionStatus.DEFERRED
    assert stale_rec.reason == "capacity_telemetry_unknown_or_stale"

    # Default mining entitlement is 0 and refused without explicit contract
    mining_rv = ResourceVector(
        cpu_time_ms=500,
        peak_memory_bytes=16 * 1024 * 1024,
        custody_bytes=4096,
        custody_io_bps=1024 * 1024,
        network_bytes=0,
        deadline_epoch_ms=10_000,
        exactness_plane="exact",
        verification_required=True,
        tenant_id="tenant_1",
        workload_class="mining",
    )
    mining_grant = AuthorityGrant.issue(
        signing_key=key,
        grant_id="g_mine",
        tenant_id="tenant_1",
        workload_id="w_mine",
        owner_authority="Chronus",
        resource_vector=mining_rv,
        nonce="nonce_mine",
        issued_at_ms=1000,
        allow_live_mining=False,
    )
    mine_rec = ctrl.admit_and_execute(
        grant=mining_grant,
        resource_vector=mining_rv,
        workload_id="w_mine",
        owner_authority="Chronus",
        capacity=cap,
        mutation_fn=lambda: {"mined": True},
        postcondition_fn=lambda _: True,
        now_ms=1200,
    )
    assert mine_rec.status == AdmissionDecisionStatus.REFUSED
    assert "zero_default_entitlement" in mine_rec.reason


def test_section6_recovery_and_security_fault_injection() -> None:
    report = run_recovery_and_security_proofs()
    assert report["all_passed"] is True
    assert report["scenario_count"] == 8
    for name, passed in report["scenarios"].items():
        assert passed is True, f"Scenario failed: {name}"


def test_section7_evidence_gated_promotion_and_rollbacks() -> None:
    cand_hash = hashlib.sha256(b"candidate_build_v2").hexdigest()
    base_hash = hashlib.sha256(b"baseline_build_v1").hexdigest()

    # 1. Full valid promotion path: SHADOW -> CANARY_1 -> CANARY_5 -> CANARY_25 -> PRODUCTION_ELIGIBLE
    ctrl = PromotionGateController(
        candidate_artifact_sha256=cand_hash,
        rollback_artifact_sha256=base_hash,
    )
    drill = ctrl.test_rollback_drill()
    assert drill["rollback_drill_passed"] is True

    for stage in (
        PromotionStage.SHADOW,
        PromotionStage.CANARY_1,
        PromotionStage.CANARY_5,
        PromotionStage.CANARY_25,
    ):
        ev = StageTelemetryEvidence(
            stage=stage,
            observations=100,
            correctness_passed=True,
            exactness_passed=True,
            security_passed=True,
            recovery_passed=True,
            baseline_p99_ms=10.0,
            candidate_p99_ms=8.5,
            baseline_peak_mem_bytes=100_000_000,
            candidate_peak_mem_bytes=95_000_000,
        )
        if stage == PromotionStage.CANARY_25:
            # Missing owner approval must fail closed before reaching PRODUCTION_ELIGIBLE
            with pytest.raises(PermissionError):
                ctrl.evaluate_and_advance(
                    ev,
                    owner_approved=False,
                    qualification_ledger_passed=True,
                )
            rec = ctrl.evaluate_and_advance(
                ev,
                owner_approved=True,
                approved_by="HYBA_Principal_Engineer",
                qualification_ledger_passed=True,
            )
            assert rec.to_stage == PromotionStage.PRODUCTION_ELIGIBLE
            assert rec.traffic_percent == 100
        else:
            rec = ctrl.evaluate_and_advance(ev)
            assert not rec.hard_abort_triggered
            assert not rec.performance_rollback_triggered

    assert ctrl.current_stage == PromotionStage.PRODUCTION_ELIGIBLE

    # 2. Hard abort on exactness or security failure triggers immediate rollback
    ctrl_abort = PromotionGateController(
        candidate_artifact_sha256=cand_hash,
        rollback_artifact_sha256=base_hash,
    )
    abort_rec = ctrl_abort.evaluate_and_advance(
        StageTelemetryEvidence(
            stage=PromotionStage.SHADOW,
            observations=100,
            correctness_passed=True,
            exactness_passed=False,
            security_passed=True,
            recovery_passed=True,
            baseline_p99_ms=10.0,
            candidate_p99_ms=8.0,
            baseline_peak_mem_bytes=100_000_000,
            candidate_peak_mem_bytes=90_000_000,
        )
    )
    assert abort_rec.hard_abort_triggered is True
    assert ctrl_abort.current_stage == PromotionStage.ROLLED_BACK
    assert ctrl_abort.active_artifact_sha256 == base_hash

    # 3. Performance regression beyond threshold triggers automatic rollback
    ctrl_perf = PromotionGateController(
        candidate_artifact_sha256=cand_hash,
        rollback_artifact_sha256=base_hash,
        max_p99_regression_ratio=1.10,
    )
    perf_rec = ctrl_perf.evaluate_and_advance(
        StageTelemetryEvidence(
            stage=PromotionStage.SHADOW,
            observations=100,
            correctness_passed=True,
            exactness_passed=True,
            security_passed=True,
            recovery_passed=True,
            baseline_p99_ms=10.0,
            candidate_p99_ms=12.5,  # 1.25x > 1.10x threshold
            baseline_peak_mem_bytes=100_000_000,
            candidate_peak_mem_bytes=100_000_000,
        )
    )
    assert perf_rec.performance_rollback_triggered is True
    assert ctrl_perf.current_stage == PromotionStage.ROLLED_BACK
    assert ctrl_perf.active_artifact_sha256 == base_hash

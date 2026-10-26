"""Verification tests for the PhiEnterprise evidence, proof, and measurement contracts.

Each test encodes a constitutional contract stated in the repository's governing documents:
  - README.md ("Measurement contract" & "Evidence boundary")
  - docs/CANONICAL_PYTHIA_SEARCH_DOCTRINE.md
  - governance/canonical_mining_search.yaml
  - claims.yaml

Tested surfaces:
  - chronus.mla1517.mining.{pow,stratum_adapter,execution_router,search_plan,
    hendrix_order,dispatch_algebra,nonce_lease,geometry,lane,chooser,solver,
    coordinator,geodesic_support,resident_router,resident_search}
  - al_haras.claims_yaml & scripts.deployment_claims_gate
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib
from math import gcd
import time
from types import SimpleNamespace

import pytest

from chronus.mla1517.mining import (
    chooser as chooser_mod,
    coordinator as coordinator_mod,
    dispatch_algebra as algebra_mod,
    execution_router as router_mod,
    geometry as geometry_mod,
    hendrix_order as hendrix_mod,
    lane as lane_mod,
    nonce_lease as lease_mod,
    pow as pow_mod,
    search_plan as plan_mod,
    solver as solver_mod,
    stratum_adapter as stratum_mod,
)


def _sample_identity(generation: int = 1, fingerprint: str = "fp-genesis-001") -> plan_mod.WorkIdentity:
    return plan_mod.WorkIdentity(
        pool_session_id="sess-contract-01",
        generation=generation,
        job_id=f"job-{generation}",
        job_fingerprint=fingerprint,
        target_generation=1,
        clean_jobs=True,
        received_at=time.monotonic(),
    )


def _sample_plan(
    *,
    executor_route: str = "cpu_reference",
    nonce_order: str = router_mod.NONCE_ORDER_HENDRIX,
    base_step: int = 0,
    window: int = 64,
    generation: int = 1,
    fingerprint: str = "fp-genesis-001",
) -> plan_mod.SearchPlan:
    return plan_mod.SearchPlan(
        job_fingerprint=fingerprint,
        pool_session_id="sess-contract-01",
        generation=generation,
        base_step=base_step,
        window=window,
        extranonce2="00000001",
        lane_order=tuple(range(32)),
        preferred_face=0,
        dispatch_breadth=window,
        executor_route=executor_route,
        policy_id="m32_structured",
        evidence_refs={"contract": "test_evidence_contract"},
        created_at=time.monotonic(),
        nonce_order=nonce_order,
    )


class TestSha256dBoundary:
    """Contract: pow.py and stratum_adapter.py own compact-target decoding,
    80-byte wire-order header construction, SHA256d, and target comparison.
    Search ordering, TOE context, and recovery never alter share validity."""

    def test_sha256d_matches_independent_reference(self) -> None:
        header = bytes(range(80))
        expected = hashlib.sha256(hashlib.sha256(header).digest()).digest()
        assert pow_mod.sha256d(header) == expected

    def test_compact_target_known_genesis_value_and_fail_closed_invalid(self) -> None:
        target = pow_mod.compact_target(0x1D00FFFF)
        assert target == 0xFFFF << (8 * (0x1D - 3))
        with pytest.raises(ValueError, match="negative compact target"):
            pow_mod.compact_target(0x1D80FFFF)
        with pytest.raises(ValueError, match="zero compact target"):
            pow_mod.compact_target(0x1D000000)

    def test_genesis_block_header_exact_consensus_verification(self) -> None:
        genesis_prev = "00" * 32
        genesis_merkle = "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"
        genesis_time = 1231006505
        genesis_bits = 0x1D00FFFF
        genesis_nonce = 2083236893

        target = pow_mod.compact_target(genesis_bits)
        header = pow_mod.build_header(
            1, genesis_prev, genesis_merkle, genesis_time, genesis_bits, genesis_nonce
        )
        assert len(header) == 80
        assert pow_mod.check_pow(header, target) is True
        block_hash_be = pow_mod.sha256d(header)[::-1].hex()
        assert block_hash_be == "000000000019d6689c085ae165831e934ff763ae46a2a6c172b3f1b60a8ce26f"

        wrong_header = pow_mod.build_header(
            1, genesis_prev, genesis_merkle, genesis_time, genesis_bits, genesis_nonce + 1
        )
        assert pow_mod.check_pow(wrong_header, target) is False

    def test_check_pow_rejects_malformed_header_and_nonpositive_target(self) -> None:
        with pytest.raises(ValueError, match="exactly 80 bytes"):
            pow_mod.check_pow(b"\x00" * 79, 1)
        with pytest.raises(ValueError, match="target must be positive"):
            pow_mod.check_pow(b"\x00" * 80, 0)

    def test_lucas_execution_scale_gate_enforced(self) -> None:
        valid_rung = pow_mod.LUCAS_EXECUTION_SCALE_INDICES[0]
        assert pow_mod.require_lucas_execution_scale(valid_rung) == valid_rung
        with pytest.raises(pow_mod.LucasScaleError):
            pow_mod.require_lucas_execution_scale(-999)
        with pytest.raises(pow_mod.LucasScaleError):
            pow_mod.require_lucas_execution_scale(True)

    def test_stratum_proof_adapter_stale_job_and_above_target_fail_closed(self) -> None:
        adapter = stratum_mod.StratumProofAdapter()
        adapter.handle_subscribe_result([[], "08000002", 4])
        adapter.handle_message({"method": "mining.set_difficulty", "params": [1]})
        notify_params = [
            "job-1",
            "00" * 32,
            "01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff08",
            "ffffffff0100f2052a010000001976a914000000000000000000000000000000000000000088ac00000000",
            [],
            "20000000",
            "1d00ffff",
            "64000000",
            True,
        ]
        adapter.handle_message({"method": "mining.notify", "params": notify_params})

        # Clean job "job-2" invalidates "job-1"
        notify_params_2 = list(notify_params)
        notify_params_2[0] = "job-2"
        notify_params_2[8] = True
        adapter.handle_message({"method": "mining.notify", "params": notify_params_2})

        with pytest.raises(stratum_mod.StaleJobError):
            adapter.validate_candidate(
                job_id="job-1", extranonce2="00000001", ntime="64000000", nonce=0
            )

        # Tightening target to 1 forces above-target rejection on job-2
        adapter.set_exact_target(1)
        with pytest.raises(stratum_mod.TargetError, match="does not meet negotiated target"):
            adapter.validate_candidate(
                job_id="job-2", extranonce2="00000001", ntime="64000000", nonce=0
            )


class TestEvidenceHierarchyAndProvenance:
    """Contract: Evidence tiers are strictly separated.
    Requested route != Executed route is explicit, fallbacks are never silent,
    and every device candidate is independently rechecked on the host."""

    def test_unbound_opencl_falls_back_to_cpu_reference_with_explicit_reason(self) -> None:
        hasher = SimpleNamespace(
            backend="cpu_reference",
            device="host-cpu",
            vendor="python",
            grind_batch=64,
            launches=0,
            kernel_ms=0.0,
        )
        router = router_mod.ExecutionRouter(
            hasher=hasher,
            cpu_executor=lambda h, t, s, c: router_mod.sha256d_scan(h, t, range(s, s + c)),
            nonce_order=lambda p: p.nonce_order,
        )
        plan = _sample_plan(executor_route="opencl_m32", window=32)
        header = b"\x00" * 80
        impossible_target = (1).to_bytes(32, "little")

        record, candidate = router.execute_plan(plan, header, impossible_target)
        assert candidate is None
        assert record.requested_route == "opencl_m32"
        assert record.executed_route == "cpu_reference"
        assert record.fallback_reason == plan_mod.FallbackReason.OPENCL_UNAVAILABLE.value
        assert record.completion_state is plan_mod.CompletionState.FALLBACK_COMPLETE
        assert record.evidence_class is plan_mod.EvidenceClass.SOFTWARE_VERIFIED
        assert record.evidence_class is not plan_mod.EvidenceClass.HARDWARE_EXECUTED
        assert record.completed_work_items == 32

    def test_bound_opencl_without_kernel_handle_falls_back_with_kernel_unavailable(self) -> None:
        hasher = SimpleNamespace(
            backend="opencl:0",
            device="gfx1103",
            vendor="AMD",
            grind_batch=64,
            k_m32=None,
            launches=0,
            kernel_ms=0.0,
        )
        router = router_mod.ExecutionRouter(
            hasher=hasher,
            cpu_executor=lambda h, t, s, c: router_mod.sha256d_scan(h, t, range(s, s + c)),
            nonce_order=lambda p: p.nonce_order,
        )
        plan = _sample_plan(executor_route="opencl_m32", window=32)
        decision = router.decide_route(plan)
        assert decision.requested_route is plan_mod.ExecutionRoute.opencl_m32
        assert decision.executed_route is plan_mod.ExecutionRoute.cpu_reference
        assert decision.fallback_reason is plan_mod.FallbackReason.KERNEL_UNAVAILABLE

    def test_false_device_winner_fails_closed_with_device_result_mismatch(self) -> None:
        class _LyingDeviceHasher:
            backend = "opencl:0"
            device = "mock-opencl"
            vendor = "test"
            grind_batch = 32
            m32_window_max = 32
            k_m32 = object()
            hendrix_on_device = True
            launches = 0
            kernel_ms = 0.0

            def grind_target_hendrix(
                self, header, target_be, base_step, window, stride, position, count
            ):
                self.launches += 1
                self.kernel_ms += 1.25
                # Return a bogus digest that does not match SHA256d(header)
                return base_step, b"\x00" * 32, count

        hasher = _LyingDeviceHasher()
        router = router_mod.ExecutionRouter(
            hasher=hasher,
            cpu_executor=lambda h, t, s, c: (None, None, c),
            nonce_order=lambda p: p.nonce_order,
        )
        plan = _sample_plan(executor_route="opencl_m32", window=32)
        header = b"\x11" * 80
        easy_target = b"\xff" * 32

        record, candidate = router.execute_plan(plan, header, easy_target)
        assert candidate is None
        assert record.locally_valid_shares == 0
        assert record.completion_state is plan_mod.CompletionState.DEVICE_ERROR
        assert record.device_error == router_mod.DEVICE_RESULT_MISMATCH


class TestBijectiveTraversalAndLeaseAlgebra:
    """Contract: Hendrix coprime stride and M32 lane permutations are exact
    bijections of the leased window. Clean-job / freshness changes invalidate
    in-flight chunks without claiming full completion."""

    @pytest.mark.parametrize("window", [32, 64, 128, 600, 1364])
    def test_hendrix_schedule_is_bijection_of_window(self, window: int) -> None:
        schedule = hendrix_mod.hendrix_schedule(window)
        assert gcd(schedule.stride, window) == 1
        base = 1024
        visited = hendrix_mod.hendrix_nonces(base, schedule, 0, window)
        assert len(visited) == window
        assert sorted(visited) == list(range(base, base + window))

    def test_m32_solver_both_orderings_preserve_complete_lane_bijection(self) -> None:
        solver = solver_mod.M32SearchSolver()
        for ordering in ("m32_lane_order", "exhaustive"):
            solver.set_candidate_ordering(ordering)
            pairs = list(solver.candidates(start_nonce=0, budget=64))
            assert len(pairs) == 64
            epoch0_nonces = [n for n, _ in pairs[:32]]
            epoch1_nonces = [n for n, _ in pairs[32:64]]
            assert sorted(epoch0_nonces) == list(range(0, 32))
            assert sorted(epoch1_nonces) == list(range(32, 64))

        solver.set_lane_start_offset(17)
        first_nonce, first_lane = next(solver.candidates(start_nonce=0, budget=1))
        assert first_lane == 17
        assert first_nonce == 17

    def test_dispatch_algebra_certifies_valid_hendrix_and_refuses_bad_header(self) -> None:
        window = 600
        schedule = hendrix_mod.hendrix_schedule(window)
        header = b"\x00" * 80
        target_le = b"\xff" * 32
        cert = algebra_mod.certify_dispatch(
            plan_id="plan-01",
            job_id="job-01",
            base_step=0,
            window=window,
            lane_order=tuple(range(32)),
            header=header,
            target_le=target_le,
            ceiling=1364,
            nonce_order=router_mod.NONCE_ORDER_HENDRIX,
            route="cpu_reference",
            hendrix=schedule,
        )
        assert cert["ok"] is True
        assert cert["refusal"] is None
        assert cert["hendrix"]["coprime"] is True
        assert cert["hendrix"]["scale_matches_lucas"] is True

        bad_cert = algebra_mod.certify_dispatch(
            plan_id="plan-02",
            job_id="job-01",
            base_step=0,
            window=window,
            lane_order=tuple(range(32)),
            header=b"\x00" * 76 + b"\x01\x00\x00\x00",
            target_le=target_le,
            ceiling=1364,
            nonce_order=router_mod.NONCE_ORDER_HENDRIX,
            route="cpu_reference",
            hendrix=schedule,
        )
        assert bad_cert["ok"] is False
        assert "header_nonce_not_zeroed" in (bad_cert["refusal"] or "")

    def test_lease_ledger_prevents_overlap_and_invalidates_on_rebind(self) -> None:
        ledger = lease_mod.NonceLeaseLedger(alignment=32)
        id1 = _sample_identity(generation=1, fingerprint="fp-1")
        ledger.bind(id1.key, id1.generation, work_space="ws-1")

        l1 = ledger.reserve_range("lease-1", "00000001", 0, 64)
        assert l1.state is plan_mod.LeaseState.RESERVED
        with pytest.raises(lease_mod.LeaseConflict, match="overlaps"):
            ledger.reserve_range("lease-overlap", "00000001", 32, 64)

        ledger.begin("lease-1", id1.key)
        assert ledger.complete("lease-1") is True
        with pytest.raises(lease_mod.LeaseConflict, match="overlaps completed coverage"):
            ledger.reserve_range("lease-dup", "00000001", 0, 32)

        l2 = ledger.reserve_range("lease-2", "00000001", 64, 64)
        assert l2.state is plan_mod.LeaseState.RESERVED
        id2 = _sample_identity(generation=2, fingerprint="fp-2")
        invalidated = ledger.bind(id2.key, id2.generation, work_space="ws-2")
        assert invalidated == 1
        assert ledger.get("lease-2").state is plan_mod.LeaseState.INVALIDATED

    def test_midflight_freshness_loss_invalidates_remaining_chunks(self) -> None:
        hasher = SimpleNamespace(
            backend="cpu_reference",
            device="host-cpu",
            vendor="python",
            grind_batch=32,
            launches=0,
            kernel_ms=0.0,
        )
        router = router_mod.ExecutionRouter(
            hasher=hasher,
            cpu_executor=lambda h, t, s, c: router_mod.sha256d_scan(h, t, range(s, s + c)),
            nonce_order=lambda p: p.nonce_order,
        )
        plan = _sample_plan(executor_route="cpu_reference", window=128)
        header = b"\x00" * 80
        impossible_target = (1).to_bytes(32, "little")

        checks = 0

        def _fresh_once() -> bool:
            nonlocal checks
            checks += 1
            return checks == 1

        record, candidate = router.execute_plan(
            plan, header, impossible_target, is_still_fresh=_fresh_once
        )
        assert candidate is None
        assert record.completion_state is plan_mod.CompletionState.INVALIDATED
        assert record.completed_work_items == 32
        assert record.planned_window == 128
        assert record.executed_nonce_order is None


class TestStickyFailureAndSubmissionGate:
    """Contract: Chooser throttle is sticky until recovery clears it;
    learning records only real pool outcomes; shadow mode blocks network writes
    while still running full SHA256d proof validation."""

    def test_chooser_sticky_throttle_and_literal_pool_learning(self) -> None:
        chooser = chooser_mod.MiningIntelligenceChooser()
        d_no_job = chooser.choose(has_job=False)
        assert d_no_job.lead == "safe"
        assert d_no_job.throttle is True

        d_errors = chooser.choose(has_job=True, error_count=2, candidate_window=[1, 2, 3, 5, 8])
        assert d_errors.throttle is True
        assert "hardware_errors_present" in d_errors.reason

        # Latched throttle remains sticky even when error_count returns to 0
        chooser.throttle = True
        d_latched = chooser.choose(has_job=True, error_count=0, candidate_window=[1, 2, 3, 5, 8])
        assert d_latched.throttle is True

        # Learn only counts boolean pool outcomes, never None
        chooser.learn(accepted=None, lead="m32_structured", job_id="job-1")
        assert chooser.accepted_count == 0
        assert chooser.rejected_count == 0
        chooser.learn(accepted=True, lead="m32_structured", job_id="job-1")
        chooser.learn(accepted=False, lead="m32_structured", job_id="job-1")
        assert chooser.accepted_count == 1
        assert chooser.rejected_count == 1

    def test_submission_permitted_gate_blocks_shadow_network_write(self) -> None:
        from manifold_pool_coordinator import ManifoldPoolCoordinator, parse_endpoint

        endpoint = parse_endpoint("stratum+tcp://127.0.0.1:3333", "local")
        coord = ManifoldPoolCoordinator(
            [endpoint], username="worker.1", password="x", submit_enabled=False
        )
        assert coord.submission_permitted() is False

        # Even with submit_enabled=False, submit_candidate runs proof validation first
        with pytest.raises(ConnectionError, match="no active Stratum client"):
            asyncio.run(
                coord.submit_candidate(
                    job_id="job-1", extranonce2="00000001", ntime="64000000", nonce=0
                )
            )


class TestClaimLanesAndSurfaceDrift:
    """Contract: All documented canonical mining modules import cleanly and
    claims.yaml / external deployment docs pass claim-register gates."""

    @pytest.mark.parametrize(
        "module_name",
        [
            "chronus.mla1517.mining.geometry",
            "chronus.mla1517.mining.lane",
            "chronus.mla1517.mining.chooser",
            "chronus.mla1517.mining.solver",
            "chronus.mla1517.mining.pow",
            "chronus.mla1517.mining.coordinator",
            "chronus.mla1517.mining.execution_router",
            "chronus.mla1517.mining.hendrix_order",
            "chronus.mla1517.mining.poincare_11d_order",
            "chronus.mla1517.mining.search_plan",
            "chronus.mla1517.mining.nonce_lease",
            "chronus.mla1517.mining.dispatch_algebra",
            "chronus.mla1517.mining.stratum_adapter",
            "chronus.mla1517.mining.geodesic_support",
            "chronus.mla1517.mining.resident_router",
            "chronus.mla1517.mining.resident_search",
        ],
    )
    def test_documented_canonical_surface_imports_cleanly(self, module_name: str) -> None:
        mod = importlib.import_module(module_name)
        assert mod is not None

    def test_claims_yaml_and_deployment_docs_gate_clean(self) -> None:
        from pathlib import Path
        from al_haras.claims_yaml import ClaimLevel, load_claims
        from scripts.deployment_claims_gate import scan

        root = Path(__file__).resolve().parents[1]
        registry = load_claims(root / "claims.yaml")
        assert registry.version >= 1
        assert len(registry.claims) > 0
        for claim in registry.claims:
            if claim.status is ClaimLevel.VERIFIED:
                assert claim.test_command, f"{claim.claim_id} missing test_command"
                assert claim.baseline, f"{claim.claim_id} missing baseline"
            if claim.status is ClaimLevel.REFUTED:
                assert claim.negative_results_log, f"{claim.claim_id} missing negative_results_log"

        findings = scan(root)
        assert findings == []

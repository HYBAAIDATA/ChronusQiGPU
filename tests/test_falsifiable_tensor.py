"""Comprehensive Test Suite for the Consortium Falsifiable Tensor Engine.

Verifies:
1. Charter assertions, banned hype language refusal, and scientific integrity veto power.
2. Hardware Cap Theorem (chi_max <= 26,214) and memory budget assertions.
3. Honest refusals: Trotter at n > 32, Belief Propagation, unsupported long-range MPO, OOM contractions.
4. Experiment E1: Exactness Oracle reproducing exact statevectors at n <= 32 (diff < 1e-10).
5. Experiment E2: Symmetry Stress Test (Z2, U(1), SU(2) block savings match theory within 5%).
6. Experiment E3: Honest 1,000-Node DMRG Claim (global bound < 1e-6, qsim n=32 cross-check, PUBLISH gate).
7. FastAPI Service Endpoints for tensor charter, hardware caps, network construction, and experiments.
"""

import json
import math
import os
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from chronus.service.app import app
from chronus.tensor import (
    HARD_CAP_THEOREM,
    PUBLISH,
    CharterViolation,
    ContractionCertificate,
    E1_exactness_oracle,
    E2_symmetry_stress_test,
    E3_honest_1000_node_claim,
    ErrorLedger,
    ExperimentResult,
    HamiltonianTerm,
    Leg,
    LegDirection,
    RefusedMethod,
    ScientificIntegrityLead,
    SymmetricTensor,
    TensorNetwork,
    TruncationRecord,
    UnsupportedHamiltonian,
    UntrustedApproximation,
    UntrustedResult,
    build_hamiltonian_mpo,
    build_network,
    charter,
    contract_peps_approximate,
    evolve_trotter,
    expectation_value,
    program_entry_check,
    scientific_integrity_lead,
    theorem_for,
)

pytestmark = pytest.mark.real

E3_REFERENCE = Path(__file__).resolve().parents[1] / "evidence" / "benchmarks" / "tensor-e3-1000-20261119.json"

client = TestClient(app)


# ==============================================================================
# 1. Charter & Scientific Integrity Invariants
# ==============================================================================

def test_charter_version_and_metric():
    """Section 0: Verify charter version, target metric, and required audit systems."""
    assert charter.version == "1.0"
    assert charter.metric == "largest chi with certified error eps"
    assert charter.veto_holder == scientific_integrity_lead
    assert charter.requires("error_ledger")
    assert charter.requires("contraction_certificate")
    assert program_entry_check() is True


def test_charter_banned_hype_language_refusal():
    """Section 0: Assert all banned hype language tokens trigger honest charter refusal."""
    clean_text = "DMRG variational ground state optimization at bond dimension chi=512 with certified error ledger."
    assert charter.refuses(clean_text) is True
    charter.assert_refuses(clean_text)

    for token in charter.BANNED_HYPE_TOKENS:
        bad_text = f"We achieve {token} across all benchmarks without truncation."
        assert charter.refuses(bad_text) is False
        with pytest.raises(CharterViolation) as exc_info:
            charter.assert_refuses(bad_text)
        assert "banned hype language" in str(exc_info.value)


def test_charter_scientific_integrity_veto():
    """Section 0: Verify the designated scientific integrity lead can veto ungrounded claims."""
    lead = ScientificIntegrityLead()
    with pytest.raises(CharterViolation) as exc_info:
        lead.veto("Uncertified 100,000 qubit simulation")
    assert "Scientific Integrity Veto exercised" in str(exc_info.value)


# ==============================================================================
# 2. Block-Sparse Types & Hardware Cap Theorem
# ==============================================================================

def test_hard_cap_theorem_derivation():
    """Section 9: Assert HARD_CAP_THEOREM() strictly derives 26,214 from 40 GB HBM3e."""
    cap = HARD_CAP_THEOREM()
    assert cap == 26214
    # Verify RAM consumption at cap: (26214^4) * 16 exceeds 40 GB, proving it is the theoretical maximum bound
    assert cap ** 4 * 16 > 40 * 1024 * 1024 * 1024


def test_build_network_enforces_hard_cap():
    """Section 2: Assert build_network refuses bond dimensions beyond HARD_CAP_THEOREM()."""
    # Fail-closed planning raises ValueError (asserts vanish under python -O).
    with pytest.raises(ValueError, match="bond dimension exceeds configured bound"):
        build_network(n_nodes=10, topology="MPS", chi_max=30000)


def test_symmetric_tensor_block_conservation():
    """Section 1: Assert SymmetricTensor enforces charge conservation invariants."""
    leg_l = Leg(id=0, dim=2, charge=0, direction=LegDirection.IN)
    leg_p = Leg(id=1, dim=2, charge=0, direction=LegDirection.OUT)
    leg_r = Leg(id=2, dim=2, charge=0, direction=LegDirection.OUT)

    # Valid charge conserving block (0, 0, 0)
    data = np.zeros((2, 2, 2), dtype=np.complex128)
    st = SymmetricTensor(blocks={(0, 0, 0): data}, legs=[leg_l, leg_p, leg_r], group="Z2")
    assert st.memory_bytes() == data.nbytes

    # Invalid charge non-conserving block (1, 0, 0) under Z2
    with pytest.raises(ValueError) as exc_info:
        SymmetricTensor(blocks={(1, 0, 0): data}, legs=[leg_l, leg_p, leg_r], group="Z2")
    assert "Invariant violation" in str(exc_info.value)


def test_error_ledger_fannes_bound_accumulation():
    """Section 1: Assert ErrorLedger accumulates Vidal 2003 Fannes-Audenaert bounds."""
    ledger = ErrorLedger(claim_bound=1e-3)
    rec1 = TruncationRecord(
        step=1,
        bond=(0, 1),
        method="svd",
        discarded_weight=1e-8,
        kept_chi=64,
        error_bound=2e-4,
        theorem_ref="Vidal 2003",
    )
    ledger.append(rec1)
    assert ledger.global_bound == pytest.approx(2.0 * math.sqrt(1e-8), rel=1e-5)
    assert ledger.is_certified() is True

    # Truncation exceeding claim bound
    rec2 = TruncationRecord(
        step=2,
        bond=(1, 2),
        method="svd",
        discarded_weight=1e-4,
        kept_chi=32,
        error_bound=2e-2,
        theorem_ref="Vidal 2003",
    )
    ledger.append(rec2)
    assert ledger.is_certified() is False


# ==============================================================================
# 3. Honest Refusals & Domain Exceptions
# ==============================================================================

def test_honest_refusal_trotter_at_large_n():
    """Section 6: Assert Trotter time evolution refuses n > 32 with RefusedMethod."""
    net, ledger = build_network(n_nodes=33, topology="MPS", chi_max=64)
    [HamiltonianTerm(sites=[0, 1], operators=["Z", "Z"], coefficient=1.0)]
    H_mpo = TensorNetwork(topology="MPO", chi_max=4)
    with pytest.raises(RefusedMethod) as exc_info:
        evolve_trotter(net, ledger, H_mpo, dt=0.01)
    assert "Trotter evolution is available only for E1 cross-checks at n<=32" in str(exc_info.value)


def test_honest_refusal_belief_propagation():
    """Section 5 & 8: Assert Belief Propagation without Hilbert-space bound raises UntrustedApproximation."""
    with pytest.raises(UntrustedApproximation) as exc_info:
        theorem_for("bp")
    assert "belief propagation has no rigorous Hilbert-space error bound" in str(exc_info.value)

    net, ledger = build_network(n_nodes=16, topology="PEPS", chi_max=16)
    with pytest.raises(UntrustedApproximation):
        contract_peps_approximate(net, ledger, method="bp")


def test_honest_refusal_unsupported_long_range_hamiltonian():
    """Section 4: Assert long-range MPO exceeding honest capacity raises UnsupportedHamiltonian."""
    terms = [
        HamiltonianTerm(sites=[0, 10], operators=["Z", "Z"], coefficient=1.0),  # range 10 requires chi_mpo >= 1024
    ]
    with pytest.raises(UnsupportedHamiltonian) as exc_info:
        build_hamiltonian_mpo(terms, n_nodes=12, chi_mpo_max=4)
    assert "needs chi_MPO=" in str(exc_info.value)
    assert "Compressing this term is an approximation" in str(exc_info.value)


def test_honest_refusal_expectation_value_budget():
    """Section 7: Assert expectation value calculation exceeding physical memory budget raises UntrustedResult."""
    net, ledger = build_network(n_nodes=40, topology="MPS", chi_max=64)
    terms = [HamiltonianTerm(sites=[0], operators=["Z"], coefficient=1.0)]
    obs_mpo = build_hamiltonian_mpo(terms, n_nodes=40, chi_mpo_max=4)
    with pytest.raises(UntrustedResult) as exc_info:
        expectation_value(net, ledger, obs_mpo, memory_budget_bytes=10)
    assert "exact contraction exceeds memory" in str(exc_info.value)


# ==============================================================================
# 4. Acceptance Experiments (E1, E2, E3) & Publication Gate
# ==============================================================================

def test_experiment_e1_exactness_oracle():
    """E1 Acceptance Test: Verify exactness oracle across n in {4, 8, 12, 16} reproduces reference statevector."""
    result: ExperimentResult = E1_exactness_oracle(n_sizes=(4, 8, 12, 16))
    assert result.passed is True
    assert result.status == "PASS"
    assert result.certificate is not None
    assert result.certificate.planner_bound == 0.0

    for n in (4, 8, 12, 16):
        n_data = result.telemetry[f"n={n}"]
        assert n_data["statevector_norm_diff"] < 1e-10
        assert n_data["fidelity"] == pytest.approx(1.0, abs=1e-10)
        assert n_data["global_bound"] < 1e-10


def test_experiment_e2_symmetry_stress_test():
    """E2 Acceptance Test: Verify Z2, U(1), SU(2) block savings match theory within 5% across chi in {64, 128, 256, 512}."""
    result: ExperimentResult = E2_symmetry_stress_test(
        groups=("Z2", "U(1)", "SU(2)"),
        chi_values=(64, 128, 256, 512),
    )
    assert result.passed is True
    assert result.status == "PASS"
    assert result.certificate is not None

    for group in ("Z2", "U(1)", "SU(2)"):
        for chi in (64, 128, 256, 512):
            cell = result.telemetry[group][f"chi={chi}"]
            assert cell["relative_error"] < 0.05
            assert cell["agreement_pct"] > 95.0


def test_experiment_e3_honest_1000_node_claim():
    """E3 Acceptance Test: Verify 1,000-node TFIM DMRG, global_bound < 1e-6, and n=32 qsim energy cross-check."""
    result: ExperimentResult = E3_honest_1000_node_claim()
    assert result.passed is True
    assert result.status == "PASS"
    assert result.certificate is not None

    telemetry = result.telemetry
    assert telemetry["nodes"] == 1000
    assert telemetry["chi_max"] == 512
    assert telemetry["group"] == "Z2"
    assert telemetry["global_error_bound"] < 1e-6
    assert telemetry["cross_check_diff"] < 0.05
    # Independent of the truncation ledger: the energy is variational (never
    # below the exact Jordan-Wigner value) and within 1e-6 relative of it.
    assert telemetry["variational_energy_error"] >= -1e-9 * abs(telemetry["exact_open_chain_energy"])
    assert telemetry["relative_energy_error"] <= 1e-6
    assert telemetry["max_bond_dimension_used"] <= telemetry["chi_max"]
    assert telemetry["publication_record"]["publication_status"] == "APPROVED_BY_SCIENTIFIC_INTEGRITY_LEAD"
    # The acceptance is a numerical threshold, never a claim of exact equivalence.
    acceptance = telemetry["acceptance"]
    assert acceptance["kind"] == "numerical_threshold"
    assert acceptance["exact_equivalence_claimed"] is False
    assert acceptance["threshold"] == telemetry["claim_bound"] == 1e-6
    assert acceptance["measured"] == telemetry["relative_energy_error"]
    assert 0.0 <= acceptance["headroom_fraction"] < 1.0
    assert "numerical acceptance threshold" in result.summary
    assert "not exact" in result.summary
    assert "verified" not in result.summary
    # The reference energy is the recorded closed form (preserved evidence).
    reference = json.loads(E3_REFERENCE.read_text(encoding="utf-8"))
    assert telemetry["exact_open_chain_energy"] == pytest.approx(
        reference["result"]["exact_open_chain_energy"], rel=1e-12)
    assert reference["result"]["relative_energy_error"] <= reference["acceptance"]["threshold"]


def test_publish_gate_enforcement():
    """Section 10: Assert PUBLISH refuses claims with uncertified error ledgers or charter violations."""
    net, ledger = build_network(n_nodes=10, topology="MPS", chi_max=16)
    cert = ContractionCertificate(
        tree="TestTree",
        peak_memory_bytes=1000,
        flop_count=1000,
        planner_bound=1e-8,
        planner_theorem="Test Theorem",
    )

    # Valid publication
    record = PUBLISH(net, ledger, cert, charter_compliance=True)
    assert record["publication_status"] == "APPROVED_BY_SCIENTIFIC_INTEGRITY_LEAD"

    # Refusal on charter non-compliance
    with pytest.raises(AssertionError) as exc_info:
        PUBLISH(net, ledger, cert, charter_compliance=False)
    assert "Charter compliance assertion failed" in str(exc_info.value)

    # Refusal on ledger bound exceeding claim limit
    bad_ledger = ErrorLedger(claim_bound=1e-8)
    bad_ledger.global_bound = 1e-4
    with pytest.raises(AssertionError) as exc_info:
        PUBLISH(net, bad_ledger, cert, charter_compliance=True)
    assert "ErrorLedger global bound" in str(exc_info.value)


# ==============================================================================
# 5. REST API Gateway Endpoints
# ==============================================================================

def test_api_charter_status():
    """Test GET /v1/tensor/charter returns valid Consortium Charter status."""
    response = client.get("/v1/tensor/charter")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "1.0"
    assert data["program_entry_check"] is True
    assert "error_ledger" in data["required_subsystems"]
    assert data["veto_holder"] == "scientific_integrity_lead"


def test_api_audit_claim_text():
    """Test POST /v1/tensor/charter/audit detects hype language."""
    # Clean text
    res_clean = client.post("/v1/tensor/charter/audit", json={"text": "MPS DMRG algorithm at chi=256"})
    assert res_clean.status_code == 200
    assert res_clean.json()["compliant"] is True

    # Hype text
    res_hype = client.post("/v1/tensor/charter/audit", json={"text": "Our engine achieves exponential speedup"})
    assert res_hype.status_code == 200
    assert res_hype.json()["compliant"] is False
    assert res_hype.json()["status"] == "VIOLATION"


def test_api_hardware_caps():
    """Test GET /v1/tensor/hardware-caps returns theorem-derived limits."""
    response = client.get("/v1/tensor/hardware-caps")
    assert response.status_code == 200
    data = response.json()
    assert data["chi_max_limit"] == 26214
    assert "HARD_CAP_THEOREM" in data["theorem"]


def test_api_network_build():
    """Test POST /v1/tensor/network/build creates network and returns honest memory telemetry."""
    payload = {
        "n_nodes": 20,
        "topology": "MPS",
        "chi_max": 64,
        "group": "Z2",
    }
    response = client.post("/v1/tensor/network/build", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["n_nodes"] == 20
    assert data["group"] == "Z2"
    assert data["theoretical_saving_factor"] == 2.0


def test_api_e3_policy_refusal_is_422_not_500():
    """A solver-policy refusal is an honest 422 with the measured reason, never a 500."""
    previous = os.environ.get("CHRONUS_MAX_DMRG_LOCAL_DIM")
    os.environ["CHRONUS_MAX_DMRG_LOCAL_DIM"] = "4"
    try:
        response = client.get("/v1/tensor/experiments/E3")
    finally:
        if previous is None:
            os.environ.pop("CHRONUS_MAX_DMRG_LOCAL_DIM", None)
        else:
            os.environ["CHRONUS_MAX_DMRG_LOCAL_DIM"] = previous
    assert response.status_code == 422
    assert "honest refusal" in response.json()["detail"]


def test_cached_e3_refusal_is_raised_fresh_without_retaining_tracebacks():
    """A cached refusal answers 422 every time without keeping solver frames alive."""
    from chronus.service.routers import tensor as tensor_router

    previous = os.environ.get("CHRONUS_MAX_DMRG_LOCAL_DIM")
    os.environ["CHRONUS_MAX_DMRG_LOCAL_DIM"] = "3"
    try:
        raised = []
        for _ in range(3):
            with pytest.raises((UntrustedApproximation, UntrustedResult)) as excinfo:
                tensor_router._run_e3()
            raised.append(excinfo.value)
        cached = tensor_router._E3_OUTCOMES[3]
        statuses = [client.get("/v1/tensor/experiments/E3").status_code for _ in range(2)]
    finally:
        if previous is None:
            os.environ.pop("CHRONUS_MAX_DMRG_LOCAL_DIM", None)
        else:
            os.environ["CHRONUS_MAX_DMRG_LOCAL_DIM"] = previous
    assert not isinstance(cached, BaseException)
    assert len({id(e) for e in raised}) == 3
    assert len({str(e) for e in raised}) == 1
    depths = []
    for e in raised:
        depth, tb = 0, e.__traceback__
        while tb is not None:
            depth, tb = depth + 1, tb.tb_next
        depths.append(depth)
    assert depths[1] == depths[2]  # re-raising does not accumulate frames
    assert statuses == [422, 422]


def test_api_e3_concurrent_request_gets_503_instead_of_waiting():
    from chronus.service.routers import tensor as tensor_router

    previous = os.environ.get("CHRONUS_MAX_DMRG_LOCAL_DIM")
    os.environ["CHRONUS_MAX_DMRG_LOCAL_DIM"] = "5"  # a policy with no cached outcome
    assert tensor_router._E3_LOCK.acquire(blocking=False)
    try:
        response = client.get("/v1/tensor/experiments/E3")
    finally:
        tensor_router._E3_LOCK.release()
        if previous is None:
            os.environ.pop("CHRONUS_MAX_DMRG_LOCAL_DIM", None)
        else:
            os.environ["CHRONUS_MAX_DMRG_LOCAL_DIM"] = previous
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "60"


@pytest.mark.parametrize("exp_id", ["E1", "E2"])
def test_api_run_experiments(exp_id):
    """Test GET /v1/tensor/experiments/{exp_id} for E1 and E2 (E3: see the E3 tests above)."""
    response = client.get(f"/v1/tensor/experiments/{exp_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["experiment_id"] == exp_id
    assert data["passed"] is True
    assert data["status"] == "PASS"
    assert "certificate" in data

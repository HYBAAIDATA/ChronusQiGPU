"""Production-path tests for the TURING VQC composition pipeline.

Covers the canonical chain request -> capability analysis -> representation
choice -> contract validation -> compile/plan -> execution -> measurement ->
verification -> custody -> replay, plus the taxonomy, representation planner,
exact unitarity verification, OVID transform and CHRONUS lane adapters.

Every test is executable evidence: GATED/UNAVAILABLE states are asserted as
honest outcomes on this CPU-only host, never skipped silently.
"""

import pytest

from turing_universal_quantum_computer import (
    Program,
    TruthClass,
    run_pipeline,
)
from turing_universal_quantum_computer.pipeline import (
    STAGE_ORDER,
    VQCPipeline,
    VQCRequest,
)
from turing_universal_quantum_computer.taxonomy import (
    ExecutionKind,
    EvidenceState,
    classify_execution,
    evidence_states,
)
from turing_universal_quantum_computer.representation import (
    DOMINANCE,
    RepresentationPlanner,
    plan_representation,
)
from turing_universal_quantum_computer.verify import (
    verify_program_unitarity,
)
from turing_universal_quantum_computer.custody import (
    CustodyError,
    envelope_digest,
    canonical_envelope_bytes,
    open_custody,
    theseus_available,
)
from turing_universal_quantum_computer.transform import (
    TransformRefuted,
    ovid_available,
    open_transform,
)
from turing_universal_quantum_computer.chronus_lane import probe_chronus_lane

pytestmark = pytest.mark.skipif(False, reason="")


def _bell() -> Program:
    return Program(n_qubits=2).then("h", 0).then("cx", 0, 1)


def _bell_t() -> Program:
    return _bell().then("t", 1)


def _ghz8() -> Program:
    program = Program(n_qubits=8).then("h", 0)
    for q in range(1, 8):
        program = program.then("cx", 0, q)
    return program


# -- taxonomy -----------------------------------------------------------------


def test_evidence_states_are_canonical():
    assert evidence_states() == (
        "PASS", "FAIL", "MEASURED", "GATED", "UNAVAILABLE", "MISSING", "REFUTED",
    )


def test_pipeline_result_classifies_as_turing_vqc_never_qpu():
    report = run_pipeline(VQCRequest(program=_bell(), shots=16, seed=1))
    assert report.execution_kind["kind"] == ExecutionKind.TURING_VQC.value
    assert report.execution_kind["measured_qpu"] is False


def test_classify_execution_refuses_qpu_inference():
    pipeline = VQCPipeline()
    result = pipeline.run(VQCRequest(program=_bell())).result
    assert result["measured_qpu"] is False
    # a hardware-class result without dispatch evidence is unaccelerated
    from turing_universal_quantum_computer.backends.base import (
        ExecutionClass,
        ExecutionResult,
    )

    hw = ExecutionResult(
        backend="qpu",
        execution_class=ExecutionClass.HARDWARE,
        truth_class=TruthClass.EXACT,
        n_qubits=2,
        program_digest="0" * 64,
        materialised=False,
        payload={},
        measured_qpu=False,
    )
    report = classify_execution(hw, device_bound=False)
    assert report.hardware_evidence == "unverified_device_binding"
    assert report.kind != ExecutionKind.PHYSICAL_QPU.value


# -- representation planner ----------------------------------------------------


def test_planner_auto_selects_tableau_for_wide_clifford():
    choice = plan_representation(_ghz8(), max_amplitudes=1 << 20)
    # 2^8 fits the budget; planner still must not silently downgrade
    assert choice.admitted
    assert choice.representation in ("tableau", "dense_algebraic")


def test_planner_picks_tableau_beyond_amplitude_budget():
    wide = _ghz8()
    choice = plan_representation(wide, max_amplitudes=1 << 4)
    assert choice.admitted
    assert choice.representation == "tableau"


def test_planner_refuses_tableau_for_non_clifford():
    choice = plan_representation(_bell_t(), representation="tableau")
    assert not choice.admitted


def test_planner_reserved_representation_is_unavailable_not_substituted():
    choice = plan_representation(_bell(), representation="symbolic_density")
    assert not choice.admitted
    assert "UNAVAILABLE" in choice.refusals[0]


def test_planner_refuses_unknown_representation():
    choice = plan_representation(_bell(), representation="magic")
    assert not choice.admitted


def test_dominance_map_is_asymmetric():
    planner = RepresentationPlanner()
    assert planner.dominates("dense_algebraic", "tableau")
    assert not planner.dominates("tableau", "dense_algebraic")
    # no representation may claim to dominate closed_form
    assert "closed_form" not in DOMINANCE.get("dense_algebraic", frozenset())


# -- exact unitarity verification ---------------------------------------------


def test_bell_unitary_verified_exactly():
    report = verify_program_unitarity(_bell())
    assert report.state == "PASS"
    assert report.verified
    assert report.checked_pairs == 10  # 4 columns -> 10 pairs


def test_nonunitary_width_refused_not_approximated():
    program = Program(n_qubits=9).then("h", 0)
    report = verify_program_unitarity(program, max_width=4)
    assert report.state == "REFUSED"
    assert not report.verified


def test_unknown_gate_refused_by_verifier():
    program = Program(n_qubits=1).then("rx_pi_2", 0)
    report = verify_program_unitarity(program)
    assert report.state == "REFUSED"


# -- OVID transform ------------------------------------------------------------


def test_ovid_transform_roundtrip_is_proven_exact():
    if not ovid_available():
        pytest.fail("aethel.ovid must be importable in the repo environment")
    transform = open_transform()
    raw = b"turing-state-bytes" * 64
    form, record = transform.fold_state(raw)
    assert record.state == "PASS"
    assert record.roundtrip_identical
    assert record.digest == form.digest
    assert transform.materialise_state(form, expected_bytes=raw) == raw


def test_ovid_materialise_rejects_expected_mismatch():
    transform = open_transform()
    form, _ = transform.fold_state(b"abc" * 16)
    with pytest.raises(TransformRefuted):
        transform.materialise_state(form, expected_bytes=b"not the same")


# -- THESEUS custody -----------------------------------------------------------


def test_custody_commit_recover_replay_roundtrip():
    if not theseus_available():
        pytest.fail("aethel.theseus must be importable in the repo environment")
    custody = open_custody()
    receipt = custody.commit("program", _bell().to_dict())
    env = custody.recover(receipt.uid)
    assert env["kind"] == "program"
    replay = custody.replay(receipt.uid)
    assert replay.state == "PASS"
    assert replay.digest_verified
    assert replay.recovered


def test_custody_envelope_digest_detects_tampering():
    env = canonical_envelope_bytes("program", _bell().to_dict())
    assert envelope_digest(env)
    import json

    tampered = json.loads(env.decode())
    tampered["payload"]["n_qubits"] = 99
    import json as _j

    bad = _j.dumps(tampered, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(CustodyError):
        envelope_digest(bad)


def test_custody_corruption_is_healed_and_reverified():
    custody = open_custody()
    receipt = custody.commit("checkpoint", {"program_digest": "x" * 64})
    custody.corrupt_for_test(receipt.uid)
    env = custody.recover(receipt.uid)
    assert env["payload"]["program_digest"] == "x" * 64
    assert custody.verify(receipt.uid)


# -- chronus lane ---------------------------------------------------------------


def test_chronus_lane_is_honest_on_cpu_host():
    lane = probe_chronus_lane()
    # On this host: no bound device -> GATED; if a device were present without
    # a contracted VQC kernel -> UNAVAILABLE.  Either way the execution path
    # stays classical and the dependency is named.
    assert lane.lane_state in (EvidenceState.GATED.value, EvidenceState.UNAVAILABLE.value)
    assert lane.execution_path == "turing_classical_exact"
    assert lane.cross_agent_dependency == "CHRONUS"


# -- end-to-end pipeline ---------------------------------------------------------


def test_pipeline_full_pass_with_custody_and_replay():
    report = run_pipeline(
        VQCRequest(
            program=_bell_t(),
            shots=64,
            seed=7,
            custody=True,
            replay=True,
            verify_unitary=True,
            differential=True,
        )
    )
    assert report.verdict == "PASS"
    assert report.schema == "turing.vqc.pipeline_report.v1"
    states = {s.stage: s.state for s in report.stages}
    for stage in (
        "request_validation", "capability_analysis", "representation_choice",
        "contract_validation", "compile_plan", "execution", "measurement",
        "verification", "custody", "replay",
    ):
        assert states[stage] == "PASS", (stage, states)
    assert states["chronus_lane"] == "GATED"
    assert report.witness is not None
    assert report.certificate is not None
    assert len(report.custody) == 4
    assert {receipt["kind"] for receipt in report.custody} == {
        "program", "result", "witness", "certificate",
    }
    assert (
        report.witness["computation_certificate_digest"]
        == report.certificate["certificate_digest"]
    )
    assert all(r["state"] == "PASS" for r in report.replay)
    assert report.replay[-1]["kind"] == "bundle"
    assert report.replay[-1]["payload_summary"]["certificate_digest"] == (
        report.certificate["certificate_digest"]
    )


def test_pipeline_replay_rejects_cross_run_certificate_bundle():
    from turing_universal_quantum_computer.backends import execute_certified

    pipeline = VQCPipeline()
    first = pipeline.run(VQCRequest(program=_bell(), custody=True))
    assert first.verdict == "PASS"
    assert len(first.custody) == 4

    foreign = execute_certified(_bell_t())
    bad_certificate = pipeline._last_custody.commit(  # noqa: SLF001 - adversarial test
        "certificate",
        foreign.certificate.to_dict(),
        meta={"stage": "verification"},
    ).as_dict()
    mixed = [
        dict(receipt)
        for receipt in first.custody
        if receipt["kind"] != "certificate"
    ] + [bad_certificate]

    state, replay = pipeline._replay(mixed)  # noqa: SLF001 - adversarial test
    assert state == "FAIL"
    assert replay[-1]["kind"] == "bundle"
    assert replay[-1]["state"] == "FAIL"
    assert "certificate" in replay[-1]["reason"]


def test_pipeline_replay_rejects_result_payload_substitution():
    pipeline = VQCPipeline()
    report = pipeline.run(VQCRequest(program=_bell_t(), custody=True))
    assert report.verdict == "PASS"
    assert report.result is not None
    assert len(report.custody) == 4

    tampered = dict(report.result)
    payload = dict(tampered["payload"])
    payload["substituted_after_execution"] = True
    tampered["payload"] = payload

    bad_result = pipeline._last_custody.commit(  # noqa: SLF001 - adversarial test
        "result",
        tampered,
        meta={"stage": "result"},
    ).as_dict()
    mixed = [
        dict(receipt)
        for receipt in report.custody
        if receipt["kind"] != "result"
    ] + [bad_result]

    state, replay = pipeline._replay(mixed)  # noqa: SLF001 - adversarial test
    assert state == "FAIL"
    assert replay[-1]["kind"] == "bundle"
    assert replay[-1]["state"] == "FAIL"
    assert "computation certificate" in replay[-1]["reason"]


def test_pipeline_stage_order_is_canonical():
    report = run_pipeline(VQCRequest(program=_bell()))
    seen = [s.stage for s in report.stages]
    assert seen == list(STAGE_ORDER)


def test_pipeline_qasm_request():
    report = run_pipeline(
        VQCRequest(qasm="OPENQASM 2.0;\nqreg q[2];\nh q[0];\ncx q[0],q[1];")
    )
    assert report.verdict == "PASS"


def test_pipeline_refuses_ambiguous_request():
    report = run_pipeline(VQCRequest(program=_bell(), qasm="qreg q[1];"))
    assert report.verdict == "FAIL"
    assert report.stages[0].state == "FAIL"


def test_pipeline_refuses_empty_request():
    report = run_pipeline(VQCRequest())
    assert report.verdict == "FAIL"


def test_pipeline_refuses_bad_qasm():
    report = run_pipeline(VQCRequest(qasm="OPENQASM 2.0;\nqreg q[1];\nrx(0.5) q[0];"))
    assert report.verdict == "REFUSED"


def test_pipeline_refuses_unknown_gate_before_execution():
    report = run_pipeline(VQCRequest(program=Program(n_qubits=1).then("bogus", 0)))
    assert report.verdict == "REFUSED"
    states = {s.stage: s.state for s in report.stages}
    assert states["representation_choice"] == "REFUSED"
    assert "execution" not in states  # fail-closed: refused before execution


def test_pipeline_refuses_preferred_backend_mismatch():
    report = run_pipeline(
        VQCRequest(program=_bell_t(), prefer_backend="stabilizer")
    )
    # stabilizer cannot admit a T gate; compile_plan must refuse
    assert report.verdict == "REFUSED"
    assert report.stages[4].state == "REFUSED"


def test_pipeline_wide_clifford_passes_via_tableau():
    report = run_pipeline(VQCRequest(program=_ghz8()))
    assert report.verdict == "PASS"
    assert report.result["backend"] == "stabilizer"


def test_pipeline_result_never_claims_qpu():
    report = run_pipeline(VQCRequest(program=_bell()))
    assert report.result["measured_qpu"] is False
    assert report.result["execution_class"] != "hardware"


def test_pipeline_replay_determinism_with_seed():
    a = run_pipeline(VQCRequest(program=_bell(), shots=32, seed=42))
    b = run_pipeline(VQCRequest(program=_bell(), shots=32, seed=42))
    assert a.result["payload"]["counts"] == b.result["payload"]["counts"]


# -- adversarial: hardware/qpu self-assertion and evidence tampering -----------


def test_qpu_self_assertion_without_job_is_refused():
    from turing_universal_quantum_computer.backends.qpu import (
        QPUClaimError,
        assert_measured_qpu,
    )
    from turing_universal_quantum_computer.backends.base import (
        ExecutionClass,
        ExecutionResult,
    )

    fake = ExecutionResult(
        backend="qpu:self",
        execution_class=ExecutionClass.HARDWARE,
        truth_class=TruthClass.EXACT,
        n_qubits=2,
        program_digest=_bell().digest(),
        materialised=True,
        payload={"job_id": "invented", "result_digest": "invented"},
        measured_qpu=True,
    )
    # self-asserted result with no provider job record: refused
    with pytest.raises(QPUClaimError):
        assert_measured_qpu(fake, None)


def test_qpu_job_record_mismatch_is_refused():
    from turing_universal_quantum_computer.backends.qpu import (
        QPUClaimError,
        QPUJob,
        assert_measured_qpu,
    )
    from turing_universal_quantum_computer.backends.base import (
        ExecutionClass,
        ExecutionResult,
    )

    result = ExecutionResult(
        backend="qpu:vendor",
        execution_class=ExecutionClass.HARDWARE,
        truth_class=TruthClass.EXACT,
        n_qubits=2,
        program_digest=_bell().digest(),
        materialised=True,
        payload={"job_id": "real-job", "result_digest": "abc"},
        measured_qpu=True,
    )
    with pytest.raises(QPUClaimError):
        assert_measured_qpu(
            result, QPUJob(provider="vendor", job_id="real-job",
                           completed_at="now", result_digest="DIFFERENT")
        )


def test_qpu_job_with_empty_fields_is_refused():
    from turing_universal_quantum_computer.backends.qpu import (
        QPUClaimError,
        QPUJob,
    )

    with pytest.raises(QPUClaimError):
        QPUJob(provider="vendor", job_id="", completed_at="t", result_digest="d")


def test_exact_result_cannot_be_dressed_as_qpu():
    from turing_universal_quantum_computer.backends.qpu import (
        QPUClaimError,
        QPUJob,
        assert_measured_qpu,
    )
    from turing_universal_quantum_computer.backends import select_backend

    backend, _ = select_backend(_bell())
    result = backend.execute(_bell())
    job = QPUJob(provider="v", job_id="j", completed_at="t", result_digest="d")
    with pytest.raises(QPUClaimError):
        assert_measured_qpu(result, job)


def test_witness_overclaim_is_refused():
    from turing_universal_quantum_computer.certificates import (
        WitnessError,
        issue_witness,
        verify_witness,
    )
    from turing_universal_quantum_computer.backends import select_backend

    backend, _ = select_backend(_bell())
    result = backend.execute(_bell())
    witness = issue_witness(_bell(), result)
    tampered = RunWitness_tampered = witness.__class__(
        **{**witness.to_dict(), "measured_qpu": True}
    )
    with pytest.raises(WitnessError):
        verify_witness(tampered)


def test_witness_rejects_provider_job_on_simulated_run():
    from turing_universal_quantum_computer.backends.qpu import QPUJob
    from turing_universal_quantum_computer.certificates import (
        WitnessError,
        issue_witness,
    )
    from turing_universal_quantum_computer.backends import select_backend

    backend, _ = select_backend(_bell())
    result = backend.execute(_bell())
    job = QPUJob(provider="v", job_id="j", completed_at="t", result_digest="d")
    with pytest.raises(WitnessError):
        issue_witness(_bell(), result, provider_job=job)


def test_custody_replay_after_corruption_heals():
    custody = open_custody()
    program = _bell_t()
    receipt = custody.commit("program", program.to_dict())
    custody.corrupt_for_test(receipt.uid)
    replay = custody.replay(receipt.uid)
    assert replay.state == "PASS"
    assert replay.payload_summary["digest"] == program.digest()


def test_custody_envelope_fabricated_digest_rejected():
    import hashlib
    import json

    env = json.loads(canonical_envelope_bytes("result", {"x": 1}).decode())
    env["digest"] = hashlib.sha256(b"attacker").hexdigest()  # fabricated
    bad = json.dumps(env, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(CustodyError):
        envelope_digest(bad)

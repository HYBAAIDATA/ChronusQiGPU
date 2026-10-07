"""Falsification tests for public VQC computation certificates."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json

import pytest

from turing_universal_quantum_computer.backends import (
    Program,
    QPUJob,
    QPUProvider,
    execute,
    execute_certified,
    register_provider,
    reset_providers,
)
from turing_universal_quantum_computer.certificates import (
    RunWitness,
    VQCComputationCertificate,
    WITNESS_SCHEMA_V1,
    WITNESS_SCHEMA_V2,
    WitnessError,
    issue_computation_certificate,
    issue_witness,
    replay_computation_certificate,
    verify_computation_certificate,
)
from turing_universal_quantum_computer.pipeline import VQCRequest, run_pipeline


def bell_program() -> Program:
    return Program(2).then("h", 0).then("cx", 0, 1)


def test_public_execute_always_attaches_a_certificate() -> None:
    program = bell_program()
    result = execute(program)
    assert result.certificate is not None
    certificate = VQCComputationCertificate.from_dict(result.certificate)
    assert certificate.halted
    assert certificate.steps == len(program.operations)
    assert certificate.replayable
    assert verify_computation_certificate(program, result, certificate)


def test_certified_execution_binds_witness_to_certificate() -> None:
    execution = execute_certified(bell_program())
    assert (
        execution.witness.computation_certificate_digest
        == execution.certificate.certificate_digest
    )
    assert execution.result.certificate == execution.certificate.to_dict()
    assert execution.witness.schema == WITNESS_SCHEMA_V2
    assert execution.witness.issued_at


def test_identical_exact_runs_have_identical_digests() -> None:
    first = execute_certified(bell_program())
    second = execute_certified(bell_program())
    assert first.certificate.certificate_digest == second.certificate.certificate_digest
    assert first.certificate.attestation == second.certificate.attestation
    assert first.witness.digest() == second.witness.digest()


def test_unseeded_sampling_is_normalized_to_replayable_seed_zero() -> None:
    program = bell_program()
    first = execute_certified(program, shots=64)
    second = execute_certified(program, shots=64, seed=0)
    assert first.certificate.replayable
    assert first.certificate == second.certificate
    replayed = replay_computation_certificate(
        program,
        first.certificate,
        execute,
        options={"shots": 64, "seed": 0},
    )
    assert replayed.certificate == first.certificate.to_dict()


def test_output_and_trace_tampering_fail_closed() -> None:
    execution = execute_certified(bell_program())
    bad_output = replace(execution.certificate, output="0" * 64)
    with pytest.raises(WitnessError, match="digest"):
        bad_output.verify_integrity()
    bad_trace = replace(
        execution.certificate,
        trace=tuple(reversed(execution.certificate.trace)),
    )
    with pytest.raises(WitnessError, match="Merkle"):
        bad_trace.verify_integrity()


def test_unordered_certificate_values_fail_closed() -> None:
    program = bell_program()
    result = execute(program)
    result.payload["unordered"] = {"a", "b"}
    with pytest.raises(WitnessError, match="unordered"):
        issue_computation_certificate(program, result)


def test_v1_witness_digest_remains_backward_compatible() -> None:
    program = bell_program()
    result = execute(program)
    current = issue_witness(program, result)
    payload = current.to_dict()
    payload["schema"] = WITNESS_SCHEMA_V1
    payload.pop("computation_certificate_digest")
    legacy = RunWitness.from_dict(payload)
    expected = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert legacy.digest() == expected


def test_v2_witness_timestamp_does_not_change_content_identity() -> None:
    execution = execute_certified(bell_program())
    later = replace(execution.witness, issued_at="2099-01-01T00:00:00+00:00")
    assert execution.witness.digest() == later.digest()


def test_pipeline_exposes_and_verifies_certificate() -> None:
    report = run_pipeline(VQCRequest(program=bell_program()))
    assert report.verdict == "PASS"
    assert report.certificate is not None
    certificate = VQCComputationCertificate.from_dict(report.certificate)
    assert certificate.verify_integrity()
    assert report.witness is not None
    assert (
        report.witness["computation_certificate_digest"]
        == certificate.certificate_digest
    )


def test_non_string_option_keys_do_not_alias_string_keys() -> None:
    # {1: "x"} and {"1": "x"} must not collapse into the same committed
    # canonical form — they are different inputs and must certify differently.
    program = bell_program()
    result = execute(program)
    int_keyed = issue_computation_certificate(
        program, result, options={"note": {1: "x"}}
    )
    str_keyed = issue_computation_certificate(
        program, result, options={"note": {"1": "x"}}
    )
    assert int_keyed.input != str_keyed.input
    assert int_keyed.certificate_digest != str_keyed.certificate_digest


def test_map_sentinel_cannot_alias_a_tagged_mapping() -> None:
    program = bell_program()
    result = execute(program)
    tagged = issue_computation_certificate(
        program, result, options={"note": {1: "x"}}
    )
    sentinel = issue_computation_certificate(
        program, result, options={"note": {"$map": [[1, "x"]]}}
    )
    assert tagged.input != sentinel.input


def test_oversized_integer_payloads_certify_via_hex_tag() -> None:
    # state_dimension = 1 << n_qubits exceeds the decimal str() cap for large
    # legal registers; the value must still certify exactly, not fail.
    program = bell_program()
    result = execute(program)
    result.payload["state_dimension"] = 1 << 20000
    certificate = issue_computation_certificate(program, result)
    assert certificate.verify_integrity()
    recovered = VQCComputationCertificate.from_dict(certificate.to_dict())
    assert recovered == certificate


def test_stabilizer_certificate_declares_gf2_field() -> None:
    program = Program(64).then("h", 0).then("cx", 0, 1)
    execution = execute_certified(program, max_amplitudes=1)
    assert execution.certificate.backend == "stabilizer"
    assert execution.certificate.field == "GF2"
    assert execution.certificate.machine_type == "quantum_folded"


def test_uncertifiable_options_refuse_before_provider_submit() -> None:
    # Certificate-first means an option that can never be certified is refused
    # before the backend runs — on a provider lane, before a billable submit.
    submissions: list[dict[str, object]] = []

    def submit(program, options):
        submissions.append(dict(options))
        return QPUJob(
            provider="stub",
            job_id="job-1",
            completed_at="2026-10-06T00:00:00+00:00",
            result_digest="0" * 64,
        )

    register_provider(
        QPUProvider(name="stub", submit=submit, configured=True)
    )
    try:
        with pytest.raises(WitnessError, match="unordered"):
            execute_certified(
                bell_program(),
                prefer="qpu",
                shots=8,
                seed=0,
                bad_option={1, 2},
            )
    finally:
        reset_providers()
    assert submissions == []


def test_pipeline_refuses_uncanonizable_options_before_execution() -> None:
    report = run_pipeline(
        VQCRequest(program=bell_program(), readout={0, 1})  # type: ignore[arg-type]
    )
    assert report.verdict == "REFUSED"
    stage = next(s for s in report.stages if s.stage == "execution")
    assert stage.state == "REFUSED"
    assert "before backend submission" in stage.detail

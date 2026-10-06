"""Falsification tests for public VQC computation certificates."""

from __future__ import annotations

from dataclasses import replace

import pytest

from turing_universal_quantum_computer.backends import (
    Program,
    execute,
    execute_certified,
)
from turing_universal_quantum_computer.certificates import (
    VQCComputationCertificate,
    WitnessError,
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

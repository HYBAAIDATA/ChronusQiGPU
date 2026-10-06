from __future__ import annotations

from dataclasses import replace

import pytest

from turing_universal_quantum_computer.turing_core.specification import (
    Direction,
    ExactField,
    MachineDescription,
    MachineType,
    Transition,
    TuringSpecError,
    certify_fold,
    execute,
    replay,
    verify_fold_replay,
    verify_machine,
)


def increment_machine() -> MachineDescription:
    return MachineDescription(
        name="unary-increment",
        machine_type=MachineType.CLASSICAL_DETERMINISTIC,
        field=ExactField.GF2,
        states=("scan", "accept", "reject"),
        alphabet=("1", "_"),
        blank="_",
        start_state="scan",
        accept_states=("accept",),
        reject_states=("reject",),
        transitions=(
            Transition("scan", "1", "scan", "1", Direction.RIGHT),
            Transition("scan", "_", "accept", "1", Direction.STAY),
        ),
    )


def test_machine_is_total_and_computation_replays() -> None:
    machine = increment_machine()
    assert verify_machine(machine)
    result = execute(machine, tuple("111"), max_steps=8)
    assert result.certificate.halted
    assert result.certificate.halt_reason == "accept"
    assert result.certificate.steps == 4
    assert result.final_configuration.tape == ((0, "1"), (1, "1"), (2, "1"), (3, "1"))
    assert replay(machine, tuple("111"), result.certificate, max_steps=8) == result


def test_missing_transition_fails_closed() -> None:
    machine = replace(increment_machine(), transitions=(increment_machine().transitions[0],))
    with pytest.raises(TuringSpecError, match="not total"):
        verify_machine(machine)


def test_step_bound_does_not_claim_non_halting_proof() -> None:
    machine = MachineDescription(
        name="right-forever",
        machine_type=MachineType.CLASSICAL_DETERMINISTIC,
        field=ExactField.GF2,
        states=("run", "accept"),
        alphabet=("_",),
        blank="_",
        start_state="run",
        accept_states=("accept",),
        reject_states=(),
        transitions=(Transition("run", "_", "run", "_", Direction.RIGHT),),
    )
    result = execute(machine, (), max_steps=3)
    assert not result.certificate.halted
    assert result.certificate.halt_reason == "step_limit"
    assert result.certificate.steps == 3


def test_certificate_tampering_is_detected() -> None:
    result = execute(increment_machine(), ("1",), max_steps=4)
    tampered = replace(result.certificate, output_digest="0" * 64)
    with pytest.raises(TuringSpecError, match="certificate digest"):
        tampered.verify_integrity()
    reordered = replace(result.certificate, trace=tuple(reversed(result.certificate.trace)))
    with pytest.raises(TuringSpecError, match="Merkle"):
        reordered.verify_integrity()


def _fold(raw: bytes) -> bytes:
    return raw[::-1]


def _unfold(folded: bytes, original_len: int) -> bytes:
    return folded[::-1][:original_len]


def test_fold_certificate_is_exact_and_replayable() -> None:
    source = bytes(range(32))
    folded, certificate = certify_fold(
        source,
        fold=_fold,
        unfold=_unfold,
        algorithm="test-reverse-v1",
    )
    assert verify_fold_replay(source, folded, certificate, unfold=_unfold)
    with pytest.raises(TuringSpecError, match="fold replay"):
        verify_fold_replay(source, folded + b"x", certificate, unfold=_unfold)


def test_machine_type_compatibility_fails_closed() -> None:
    machine = replace(increment_machine(), machine_type=MachineType.QUANTUM_UNITARY)
    with pytest.raises(TuringSpecError, match="compatible backend"):
        execute(machine, ("1",), max_steps=2)

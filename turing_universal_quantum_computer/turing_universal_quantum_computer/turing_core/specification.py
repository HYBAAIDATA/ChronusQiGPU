"""Machine-checkable Turing-core specification, execution, and certification.

This module deliberately models a small, explicit deterministic machine.  It
does not claim to decide halting in general: executions are either halted by a
declared accept/reject state or stopped by an explicit step bound.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, is_dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


class TuringSpecError(ValueError):
    """A machine, certificate, or fold fails closed."""


class MachineType(str, Enum):
    CLASSICAL_DETERMINISTIC = "classical_deterministic"
    CLASSICAL_NONDETERMINISTIC = "classical_nondeterministic"
    QUANTUM_UNITARY = "quantum_unitary"
    QUANTUM_FOLDED = "quantum_folded"
    HYBRID = "hybrid"


class ExactField(str, Enum):
    Q = "Q"
    Q_I = "Q_i"
    Q_SQRT2 = "Q_sqrt2"
    Q_ZETA8 = "Q_zeta8"
    GF2 = "GF2"
    FLOAT = "float"
    MIXED = "mixed"
    MISSING = "missing"


class Direction(str, Enum):
    LEFT = "L"
    STAY = "S"
    RIGHT = "R"


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bytes):
        return {"$bytes": value.hex()}
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise TuringSpecError(f"unsupported canonical value: {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    """Serialize without platform, locale, insertion-order, or float variance."""
    return json.dumps(
        _jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def domain_digest(domain: str, value: Any) -> str:
    prefix = b"turing-core-v1\0" + domain.encode("ascii") + b"\0"
    return hashlib.sha256(prefix + canonical_bytes(value)).hexdigest()


def merkle_root(leaves: Sequence[Any]) -> str:
    """Return an ordered, domain-separated SHA-256 Merkle root.

    An empty tree commits to ``turing-merkle-empty-v1``.  Odd levels duplicate
    their final node; changing order therefore changes the root.
    """
    if not leaves:
        return hashlib.sha256(b"turing-merkle-empty-v1").hexdigest()
    level = [
        hashlib.sha256(b"turing-merkle-leaf-v1\0" + canonical_bytes(leaf)).digest()
        for leaf in leaves
    ]
    while len(level) > 1:
        if len(level) & 1:
            level.append(level[-1])
        level = [
            hashlib.sha256(b"turing-merkle-node-v1\0" + level[i] + level[i + 1]).digest()
            for i in range(0, len(level), 2)
        ]
    return level[0].hex()


@dataclass(frozen=True, order=True)
class Transition:
    state: str
    symbol: str
    next_state: str
    write_symbol: str
    direction: Direction


@dataclass(frozen=True)
class MachineDescription:
    name: str
    machine_type: MachineType
    field: ExactField
    states: tuple[str, ...]
    alphabet: tuple[str, ...]
    blank: str
    start_state: str
    accept_states: tuple[str, ...]
    reject_states: tuple[str, ...]
    transitions: tuple[Transition, ...]
    tape_semantics: str = "two_way_unbounded_sparse"
    clock_domain: str = "discrete_tick"

    def transition_map(self) -> dict[tuple[str, str], Transition]:
        result: dict[tuple[str, str], Transition] = {}
        for transition in self.transitions:
            key = (transition.state, transition.symbol)
            if key in result:
                raise TuringSpecError(f"duplicate transition for {key!r}")
            result[key] = transition
        return result

    def digest(self) -> str:
        return domain_digest("machine", self)


@dataclass(frozen=True)
class Configuration:
    step: int
    state: str
    head: int
    tape: tuple[tuple[int, str], ...]


@dataclass(frozen=True)
class TuringCertificate:
    schema: str
    input_digest: str
    machine_digest: str
    trace: tuple[Configuration, ...]
    output_digest: str
    halted: bool
    halt_reason: str
    steps: int
    certificate_digest: str
    attestation: str

    def unsigned_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("certificate_digest")
        return payload

    def verify_integrity(self) -> bool:
        expected_attestation = merkle_root(self.trace)
        if self.attestation != expected_attestation:
            raise TuringSpecError("trace Merkle attestation mismatch")
        expected = domain_digest("certificate", self.unsigned_payload())
        if self.certificate_digest != expected:
            raise TuringSpecError("certificate digest mismatch")
        if self.steps != max(len(self.trace) - 1, 0):
            raise TuringSpecError("step count does not match trace length")
        if not self.trace:
            raise TuringSpecError("certificate trace is empty")
        return True


@dataclass(frozen=True)
class FoldCertificate:
    schema: str
    algorithm: str
    source_digest: str
    folded_digest: str
    unfolded_digest: str
    source_length: int
    exact: bool
    attestation: str
    certificate_digest: str

    def unsigned_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("certificate_digest")
        return payload

    def verify_integrity(self) -> bool:
        if not self.exact:
            raise TuringSpecError("fold is not exact")
        expected = domain_digest("fold-certificate", self.unsigned_payload())
        if self.certificate_digest != expected:
            raise TuringSpecError("fold certificate digest mismatch")
        return True


@dataclass(frozen=True)
class Execution:
    certificate: TuringCertificate
    final_configuration: Configuration


def verify_machine(machine: MachineDescription) -> bool:
    if machine.machine_type is not MachineType.CLASSICAL_DETERMINISTIC:
        raise TuringSpecError(
            "this verifier executes classical_deterministic machines only; "
            "other declared types require a compatible backend"
        )
    states = set(machine.states)
    alphabet = set(machine.alphabet)
    if not states or not alphabet:
        raise TuringSpecError("states and alphabet must be non-empty")
    if len(states) != len(machine.states) or len(alphabet) != len(machine.alphabet):
        raise TuringSpecError("states and alphabet must not contain duplicates")
    if machine.blank not in alphabet:
        raise TuringSpecError("blank symbol is outside the alphabet")
    if machine.start_state not in states:
        raise TuringSpecError("start state is outside the state set")
    halting = set(machine.accept_states) | set(machine.reject_states)
    if not halting or not halting <= states:
        raise TuringSpecError("halting states must be a non-empty subset of states")
    if set(machine.accept_states) & set(machine.reject_states):
        raise TuringSpecError("accept and reject states must be disjoint")
    transitions = machine.transition_map()
    for transition in transitions.values():
        if transition.next_state not in states:
            raise TuringSpecError("transition targets an unknown state")
        if transition.write_symbol not in alphabet:
            raise TuringSpecError("transition writes an unknown symbol")
    expected = {
        (state, symbol)
        for state in states - halting
        for symbol in alphabet
    }
    actual = set(transitions)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise TuringSpecError(f"transition table is not total: missing={missing}, extra={extra}")
    return True


def _configuration(
    step: int, state: str, head: int, tape: Mapping[int, str], blank: str
) -> Configuration:
    cells = tuple(
        sorted(
            (position, symbol)
            for position, symbol in tape.items()
            if symbol != blank
        )
    )
    return Configuration(step=step, state=state, head=head, tape=cells)


def execute(
    machine: MachineDescription,
    input_symbols: Sequence[str],
    *,
    max_steps: int,
) -> Execution:
    """Execute and always return a content-addressed certificate.

    ``max_steps`` is the explicit answer to the halting problem boundary.
    A non-halted result says ``step_limit``; it is not a proof of divergence.
    """
    verify_machine(machine)
    if max_steps < 0:
        raise TuringSpecError("max_steps must be non-negative")
    alphabet = set(machine.alphabet)
    if any(symbol not in alphabet or symbol == machine.blank for symbol in input_symbols):
        raise TuringSpecError("input contains a blank or out-of-alphabet symbol")
    tape = {index: symbol for index, symbol in enumerate(input_symbols)}
    state = machine.start_state
    head = 0
    trace = [_configuration(0, state, head, tape, machine.blank)]
    transition_map = machine.transition_map()
    accept = set(machine.accept_states)
    reject = set(machine.reject_states)
    halt_reason = ""

    while len(trace) - 1 < max_steps and state not in accept and state not in reject:
        symbol = tape.get(head, machine.blank)
        transition = transition_map[(state, symbol)]
        if transition.write_symbol == machine.blank:
            tape.pop(head, None)
        else:
            tape[head] = transition.write_symbol
        if transition.direction is Direction.LEFT:
            head -= 1
        elif transition.direction is Direction.RIGHT:
            head += 1
        state = transition.next_state
        trace.append(_configuration(len(trace), state, head, tape, machine.blank))

    halted = state in accept or state in reject
    if state in accept:
        halt_reason = "accept"
    elif state in reject:
        halt_reason = "reject"
    else:
        halt_reason = "step_limit"

    input_digest = domain_digest("input", tuple(input_symbols))
    output_payload = {"state": state, "head": head, "tape": trace[-1].tape}
    unsigned = {
        "schema": "turing.computation.certificate.v1",
        "input_digest": input_digest,
        "machine_digest": machine.digest(),
        "trace": tuple(trace),
        "output_digest": domain_digest("output", output_payload),
        "halted": halted,
        "halt_reason": halt_reason,
        "steps": len(trace) - 1,
        "attestation": merkle_root(trace),
    }
    certificate = TuringCertificate(
        **unsigned,
        certificate_digest=domain_digest("certificate", unsigned),
    )
    certificate.verify_integrity()
    return Execution(certificate=certificate, final_configuration=trace[-1])


def replay(
    machine: MachineDescription,
    input_symbols: Sequence[str],
    certificate: TuringCertificate,
    *,
    max_steps: int,
) -> Execution:
    certificate.verify_integrity()
    if certificate.machine_digest != machine.digest():
        raise TuringSpecError("certificate is bound to a different machine")
    if certificate.input_digest != domain_digest("input", tuple(input_symbols)):
        raise TuringSpecError("certificate is bound to different input")
    replayed = execute(machine, input_symbols, max_steps=max_steps)
    if replayed.certificate != certificate:
        raise TuringSpecError("certificate replay diverged")
    return replayed


def certify_fold(
    source: bytes,
    *,
    fold: Callable[[bytes], bytes],
    unfold: Callable[[bytes, int], bytes],
    algorithm: str,
) -> tuple[bytes, FoldCertificate]:
    folded = fold(source)
    restored = unfold(folded, len(source))
    exact = restored == source
    unsigned = {
        "schema": "turing.fold.certificate.v1",
        "algorithm": algorithm,
        "source_digest": domain_digest("fold-source", source),
        "folded_digest": domain_digest("folded", folded),
        "unfolded_digest": domain_digest("fold-unfolded", restored),
        "source_length": len(source),
        "exact": exact,
        "attestation": merkle_root((source, folded, restored)),
    }
    certificate = FoldCertificate(
        **unsigned,
        certificate_digest=domain_digest("fold-certificate", unsigned),
    )
    certificate.verify_integrity()
    return folded, certificate


def certify_t_phi_fold(source: bytes) -> tuple[bytes, FoldCertificate]:
    from .core import t_phi_fold, t_phi_unfold

    return certify_fold(
        source,
        fold=t_phi_fold,
        unfold=t_phi_unfold,
        algorithm="t_phi_gl2_zmod256_v1",
    )


def verify_fold_replay(
    source: bytes,
    folded: bytes,
    certificate: FoldCertificate,
    *,
    unfold: Callable[[bytes, int], bytes],
) -> bool:
    certificate.verify_integrity()
    restored = unfold(folded, certificate.source_length)
    checks = {
        "source": domain_digest("fold-source", source) == certificate.source_digest,
        "folded": domain_digest("folded", folded) == certificate.folded_digest,
        "unfolded": domain_digest("fold-unfolded", restored) == certificate.unfolded_digest,
        "exact": restored == source,
        "attestation": merkle_root((source, folded, restored)) == certificate.attestation,
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise TuringSpecError(f"fold replay failed: {failed}")
    return True


def write_certificate(path: str | Path, certificate: TuringCertificate | FoldCertificate) -> None:
    Path(path).write_bytes(canonical_bytes(certificate) + b"\n")

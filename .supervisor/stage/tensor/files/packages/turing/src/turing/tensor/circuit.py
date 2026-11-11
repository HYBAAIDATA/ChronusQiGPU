"""Circuit entry point: evaluate a gate list exactly as an :class:`~turing.tensor.mps.ExactMPS`."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, Sequence

from .field import Field, cyclotomic
from .mps import DEFAULT_MAX_BOND, GATE_NAMES, ExactMPS, required_order

__all__ = ["evaluate_circuit"]


def _parse(entry: object, position: int) -> tuple[str, tuple[int, ...], Any]:
    if isinstance(entry, (str, bytes)) or not isinstance(entry, Sequence) or len(entry) not in (2, 3):
        raise ValueError(f"gate {position} must be (name, qubits) or (name, qubits, params), got {entry!r}")
    name = entry[0]
    if not isinstance(name, str) or name.lower() not in GATE_NAMES:
        raise ValueError(f"gate {position} has unknown name {name!r}; known gates: {', '.join(GATE_NAMES)}")
    qubits = entry[1]
    sites = (qubits,) if isinstance(qubits, int) and not isinstance(qubits, bool) else tuple(qubits)
    params = entry[2] if len(entry) == 3 else ()
    if not isinstance(params, (Mapping, Sequence)) or isinstance(params, (str, bytes)):
        raise ValueError(f"gate {position}: params must be a sequence or a mapping")
    return name.lower(), sites, params


def evaluate_circuit(n_qubits: int, gates: Iterable[Sequence[Any]], max_bond: int = DEFAULT_MAX_BOND,
                     field: Optional[Field] = None) -> ExactMPS:
    """Evaluate a circuit exactly from |0 ... 0> on ``n_qubits`` qubits.

    ``gates`` is a list of (name, qubits, params) with names from GATE_NAMES,
    for example ("h", (0,), ()), ("cnot", (0, 1), ()), ("phase", (2,), (3, 16))
    for diag(1, zeta_16^3), or ("unitary", (0, 1), (matrix, scale)) for an
    exact matrix acting as matrix / sqrt(scale). Without an explicit field the
    register uses Q(zeta_m) with m the least common multiple of 8 and of every
    root-of-unity order the gates need. A gate whose exact bond rank would
    exceed ``max_bond`` raises ValueError; no truncated state is returned.
    """
    parsed = [_parse(entry, position) for position, entry in enumerate(gates)]
    if field is None:
        field = cyclotomic(required_order(parsed))
    register = ExactMPS(n_qubits, 2, field, max_bond)
    for name, sites, params in parsed:
        register.apply(name, sites, params)
    return register

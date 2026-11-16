"""Exact finite-field state-vector algebra over F_257 (legacy quantum-inspired namespace).

Amplitudes are elements of F_257, never floating point. The field contains
every constant the standard gate set needs, exactly:

    sqrt(2) = 60        (60^2 = 3600 = 14*257 + 2)
    1/sqrt(2) = 30      (the Hadamard normalization)
    i = 16              (16^2 = 256 = -1; the S gate phase)
    omega_8 = 4         (4^4 = -1, 4^8 = 1; the T gate phase)

Gates are exact 2x2 matrices over F_257 applied by index arithmetic across
the 2^n amplitude vector. This provides exact state evolution and circuit
equivalence verification (two circuits are equal iff their final amplitude
vectors are identical field elements). It is not a sampling simulator: over
a finite field there is no Born rule, so measurement is intentionally absent.
"""

from dataclasses import dataclass, field

P = 257
SQRT2 = 60
INV_SQRT2 = 30
I_UNIT = 16
OMEGA_8 = 4
MAX_QUBITS = 12

_GATES: dict[str, tuple[tuple[int, int], tuple[int, int]]] = {
    "X": ((0, 1), (1, 0)),
    "Z": ((1, 0), (0, P - 1)),
    "Y": ((0, P - I_UNIT), (I_UNIT, 0)),
    "H": ((INV_SQRT2, INV_SQRT2), (INV_SQRT2, P - INV_SQRT2)),
    "S": ((1, 0), (0, I_UNIT)),
    "T": ((1, 0), (0, OMEGA_8)),
}


def _element(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("amplitudes must be integers")
    return value % P


@dataclass
class StateVector:
    """An exact 2^n-amplitude state over F_257, starting from |0...0>."""

    num_qubits: int
    amplitudes: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.num_qubits, int) or isinstance(self.num_qubits, bool) \
                or not 1 <= self.num_qubits <= MAX_QUBITS:
            raise ValueError(f"num_qubits must be between 1 and {MAX_QUBITS}")
        size = 1 << self.num_qubits
        if self.amplitudes:
            if len(self.amplitudes) != size:
                raise ValueError(f"expected {size} amplitudes")
            self.amplitudes = [_element(a) for a in self.amplitudes]
        else:
            self.amplitudes = [1] + [0] * (size - 1)

    def apply(self, gate: str, qubit: int) -> "StateVector":
        if gate not in _GATES:
            raise ValueError(f"unknown gate '{gate}'; supported: {sorted(_GATES)}")
        if not isinstance(qubit, int) or not 0 <= qubit < self.num_qubits:
            raise ValueError("qubit index out of range")
        matrix = _GATES[gate]
        stride = 1 << qubit
        amps = self.amplitudes
        for base in range(0, len(amps), stride * 2):
            for offset in range(stride):
                i0, i1 = base + offset, base + offset + stride
                a0, a1 = amps[i0], amps[i1]
                amps[i0] = (matrix[0][0] * a0 + matrix[0][1] * a1) % P
                amps[i1] = (matrix[1][0] * a0 + matrix[1][1] * a1) % P
        return self

    def cnot(self, control: int, target: int) -> "StateVector":
        if control == target or not (0 <= control < self.num_qubits) \
                or not (0 <= target < self.num_qubits):
            raise ValueError("control and target must be distinct in-range qubits")
        cstride, tstride = 1 << control, 1 << target
        for index in range(len(self.amplitudes)):
            if index & cstride and not index & tstride:
                partner = index | tstride
                self.amplitudes[index], self.amplitudes[partner] = (
                    self.amplitudes[partner], self.amplitudes[index],
                )
        return self

    def equivalent(self, other: "StateVector") -> bool:
        """Exact circuit identity: equal iff every amplitude matches."""
        return self.num_qubits == other.num_qubits \
            and self.amplitudes == other.amplitudes

    def to_dict(self) -> dict:
        return {
            "field": "F_257",
            "num_qubits": self.num_qubits,
            "amplitudes": list(self.amplitudes),
        }

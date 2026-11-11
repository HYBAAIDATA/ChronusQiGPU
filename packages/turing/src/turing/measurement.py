"""Born-rule probabilities and finite-dimensional projective measurements."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .operator import LinearOperator
from .state import DEFAULT_TOLERANCE, QuantumState


def born_probabilities(state: QuantumState) -> tuple[float, ...]:
    """Return computational-basis probabilities ``|amplitude_i|**2``."""
    if not isinstance(state, QuantumState):
        raise TypeError("state must be a QuantumState")
    return tuple(abs(amplitude) ** 2 for amplitude in state.amplitudes)


@dataclass(frozen=True, slots=True)
class ProjectiveMeasurement:
    """A complete family of mutually orthogonal projectors."""

    projectors: tuple[LinearOperator, ...]
    tolerance: float = DEFAULT_TOLERANCE

    def __post_init__(self) -> None:
        projectors = tuple(self.projectors)
        if not math.isfinite(self.tolerance) or self.tolerance <= 0:
            raise ValueError("tolerance must be a positive finite number")
        if not projectors or any(not isinstance(p, LinearOperator) for p in projectors):
            raise ValueError("measurement requires one or more LinearOperator projectors")
        dimension = projectors[0].dimension
        if any(p.dimension != dimension for p in projectors):
            raise ValueError("all projectors must have the same dimension")
        for projector in projectors:
            if not projector.is_hermitian(self.tolerance):
                raise ValueError("projectors must be Hermitian")
            if not projector.compose(projector).almost_equal(projector, self.tolerance):
                raise ValueError("projectors must be idempotent")
        for i, left in enumerate(projectors):
            for right in projectors[i + 1:]:
                if not left.compose(right).almost_equal(
                    LinearOperator.from_rows(tuple(tuple(0 for _ in range(dimension))
                                                    for _ in range(dimension))),
                    self.tolerance,
                ):
                    raise ValueError("projectors must be pairwise orthogonal")
        total = LinearOperator.from_rows(tuple(
            tuple(sum(p.matrix[i][j] for p in projectors) for j in range(dimension))
            for i in range(dimension)
        ))
        if not total.almost_equal(LinearOperator.identity(dimension), self.tolerance):
            raise ValueError("projectors must sum to the identity")
        object.__setattr__(self, "projectors", projectors)

    def probabilities(self, state: QuantumState) -> tuple[float, ...]:
        """Return Born probabilities ``<psi|P_j|psi>`` for each outcome."""
        if state.dimension != self.projectors[0].dimension:
            raise ValueError("measurement and state dimensions must match")
        probabilities = tuple(
            sum(abs(amplitude) ** 2
                for amplitude in projector.apply_amplitudes(state.amplitudes))
            for projector in self.projectors
        )
        if not math.isclose(sum(probabilities), 1.0, rel_tol=0.0,
                            abs_tol=max(self.tolerance * 10, DEFAULT_TOLERANCE)):
            raise ArithmeticError("measurement probabilities do not sum to one")
        return probabilities

    def collapse(self, state: QuantumState, outcome: int) -> QuantumState:
        """Return the normalized post-measurement state for an outcome."""
        if not isinstance(outcome, int) or isinstance(outcome, bool) \
                or not 0 <= outcome < len(self.projectors):
            raise ValueError("outcome index is out of range")
        projected = self.projectors[outcome].apply_amplitudes(state.amplitudes)
        probability = sum(abs(amplitude) ** 2 for amplitude in projected)
        if probability == 0.0:
            raise ValueError("cannot condition on a zero-probability outcome")
        scale = math.sqrt(probability)
        return QuantumState(tuple(amplitude / scale for amplitude in projected))


def computational_basis_measurement(dimension: int) -> ProjectiveMeasurement:
    """Create the standard rank-one computational-basis measurement."""
    if not isinstance(dimension, int) or isinstance(dimension, bool) or dimension < 1:
        raise ValueError("dimension must be a positive integer")
    projectors = []
    for outcome in range(dimension):
        rows = tuple(tuple(1.0 if i == outcome and j == outcome else 0.0
                           for j in range(dimension)) for i in range(dimension))
        projectors.append(LinearOperator.from_rows(rows))
    return ProjectiveMeasurement(tuple(projectors))

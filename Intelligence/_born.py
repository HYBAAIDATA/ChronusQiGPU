"""Born-rule primitives shared by the Intelligence cluster.

Every learned scalar in this package is a *measurement*, not a classical
accumulator driven by an invented learning-rate constant. The conventions
here mirror the repair landed in ``resonance_intelligence.feedback_core``
(commit 90cc74d): a scalar weight is the Born readout of a qubit,

    w = <sigma_z> = |a0|^2 - |a1|^2    in [-1, 1],

and an outcome applies a unitary rotation ``R_y(theta) = exp(-i theta
sigma_y / 2)`` to that state. The rotation angle is the *measured* signal
normalised so a full-strength signal applies a quarter-turn on the Bloch
sphere — that geometric normalisation is not a tuned hyperparameter.

For multi-component learned models (feature vectors, association graphs)
the same principle is applied inside the two-dimensional plane spanned by
the model state |psi> and the measured evidence state |x>: rotating psi by
the angle that carries the measurement toward (or away from) x is a real
SU(2) unitary on that subspace — Schrödinger-evolution quantum math
realised on ``kellogg.quantum_tensor`` primitives.
"""

from __future__ import annotations

import math
from typing import Iterable, List

from kellogg.quantum_tensor import Complex, ComplexMatrix, QuantumState

# A full-strength unit signal applies a quarter-turn: the pole-to-pole
# Bloch sweep is pi and this constant is that geometric normalisation,
# not a tuned hyperparameter.
QUARTER_TURN = math.pi / 2.0


def weight_to_state(weight: float) -> QuantumState:
    """Embed a scalar weight ``w = <sigma_z>`` as the qubit ray at Bloch
    angle ``arccos(w)``.

    ``|psi> = cos(phi/2)|0> + sin(phi/2)|1>`` with ``phi = arccos(w)``, so
    the Born probabilities ``|a0|^2, |a1|^2`` reproduce
    ``w = |a0|^2 - |a1|^2`` exactly.
    """
    phi = math.acos(max(-1.0, min(1.0, float(weight))))
    return QuantumState(
        2,
        [Complex(math.cos(phi / 2), 0.0), Complex(math.sin(phi / 2), 0.0)],
    )


def rotate_weight(weight: float, angle: float) -> float:
    """Apply ``R_y(angle)`` to the weight qubit and read ``<sigma_z>`` via
    the Born rule.

    Sign convention: a positive ``angle`` rotates the Bloch vector toward
    the ``|1>`` pole (weight decreases); a negative angle rotates toward
    ``|0>`` (weight increases). Callers pass ``angle = -signal`` for a
    positive measured signal strengthening the weight.
    """
    c, s = math.cos(angle / 2), math.sin(angle / 2)
    unitary = ComplexMatrix.from_real([[c, -s], [s, c]])
    probs = weight_to_state(weight).apply_unitary(unitary).probabilities()
    return probs[0] - probs[1]


def born_evidence(positive: float, negative: float) -> float:
    """Born probability of the "positive" outcome for an evidence-encoded
    two-level state.

    The state is ``|psi> proportional to sqrt(pos+1)|0> + sqrt(neg+1)|1>``
    (unit prior evidence per outcome, i.e. the laplace-encoded ray), so

        P(positive) = (pos + 1) / (pos + neg + 2).

    This is a genuine Born-rule readout of the evidence state — with no
    observed evidence it reports the prior 0.5 of the encoded ray, which is
    the honest statement "nothing has been measured yet", not an invented
    midpoint.
    """
    pos = max(0.0, float(positive))
    neg = max(0.0, float(negative))
    return (pos + 1.0) / (pos + neg + 2.0)


def born_evidence_weight(positive: float, negative: float) -> float:
    """Born z-component of the evidence state: ``P(+) - P(-)`` in [-1, 1]."""
    pos = max(0.0, float(positive))
    neg = max(0.0, float(negative))
    return (pos - neg) / (pos + neg + 2.0)


def evidence_angle(count: int) -> float:
    """Bloch-sphere displacement of one additional evidence unit after
    ``count`` units have already been observed.

    The evidence ray for ``c`` observed negative events against the unit
    prior is ``e_c = (|0> + sqrt(c+1)|1>) / sqrt(c+2)``. One further event
    moves it to ``e_{c+1}``; the displacement is the measured arc

        sep_c = arccos |<e_c | e_{c+1}>|,

    a strictly shrinking step (posterior shrinkage) with no invented
    step size.
    """
    c = max(0, int(count))
    inner = (1.0 + math.sqrt((c + 1) * (c + 2))) / math.sqrt((c + 2) * (c + 3))
    return math.acos(min(1.0, inner))


def probability_qubit(p: float) -> QuantumState:
    """Embed a probability p in [0, 1] as the qubit
    sqrt(p)|0> + sqrt(1-p)|1>; p is the Born weight of |0>."""
    p = max(0.0, min(1.0, float(p)))
    return QuantumState(2, [Complex(math.sqrt(p), 0.0), Complex(math.sqrt(1.0 - p), 0.0)])


def adjust_probability(p: float, toward_one: bool, angle: float) -> float:
    """Rotate the probability qubit p toward the |0> (toward_one) or |1>
    pole by ``angle`` radians and read back the new Born weight.

    The rotation is a real unitary in the plane spanned by the state's
    current position and the pole, clamped at the pole — so repeated
    adjustments converge rather than overshoot.
    """
    state = probability_qubit(p)
    pole = QuantumState.from_basis(2, 0 if toward_one else 1)
    return rotate_state_in_plane(state, pole, angle).probabilities()[0]


def encode_state(vector: Iterable[float]) -> QuantumState:
    """Encode a real feature vector as a quantum state whose amplitudes are
    the vector components (unit-normalised)."""
    data: List[float] = [float(v) for v in vector]
    norm = math.sqrt(sum(v * v for v in data))
    if norm <= 0.0:
        # No measured direction: uniform superposition (maximum ignorance).
        n = max(1, len(data))
        amp = 1.0 / math.sqrt(n)
        return QuantumState(n, [Complex(amp, 0.0) for _ in range(n)])
    return QuantumState(len(data), [Complex(v / norm, 0.0) for v in data])


def rotate_state_in_plane(state: QuantumState, target: QuantumState, angle: float) -> QuantumState:
    """Rotate ``state`` toward ``target`` by ``angle`` inside the plane
    they span — a real unitary on that two-dimensional subspace.

    Decompose |x> = a|psi> + b|v> where |v> is the component of |x>
    orthogonal to |psi> (normalised). The rotation that advances psi
    toward x within span{psi, v} by angle theta is

        |psi'> = cos(theta)|psi> + sin(theta)|v>,

    which is exactly the action of the SU(2) generator i|v><psi| -
    i|psi><v| on that plane — a genuine unitary (the plane analogue of
    R_y). Sign of ``angle`` sets the direction: positive rotates toward
    the evidence state, negative rotates away.
    """

    if state.dim != target.dim:
        raise ValueError(f"state dims differ: {state.dim} vs {target.dim}")
    n = state.dim
    # a = <psi|x>. QuantumState.inner(other) returns <other|self>, so
    # state.inner(target) = <x|psi> and the coefficient is its conjugate.
    inner = state.inner(target).conj()
    # v = x - a*psi, normalised
    v: List[Complex] = [target.amplitudes[i] - inner * state.amplitudes[i] for i in range(n)]
    v_norm = math.sqrt(sum(vc.abs2() for vc in v))
    if v_norm < 1e-12:
        # Target already (anti-)parallel to state — nothing to rotate.
        return state
    v = [vc / v_norm for vc in v]
    # Clamp to the measured angular distance: rotating past the target
    # would overshoot the pole, so the applied angle never exceeds the
    # arc between the two states.
    separation = math.atan2(v_norm, inner.abs())
    angle = math.copysign(min(abs(angle), separation), angle)
    c = math.cos(angle)
    s = math.sin(angle)
    out = [state.amplitudes[i] * c + v[i] * s for i in range(n)]
    return QuantumState(n, out)


def state_to_vector(state: QuantumState) -> List[float]:
    """Read a state back as a real amplitude vector (re parts)."""
    return [a.re for a in state.amplitudes]


def fidelity_score(state: QuantumState, target: QuantumState) -> float:
    """Born overlap ``|<psi|x>|^2`` between two states — the quantum-native
    replacement for cosine similarity / dot-product scores."""
    return state.fidelity(target)

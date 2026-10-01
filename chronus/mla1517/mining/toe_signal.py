"""TOE causal signal — feed-forward path from the TOE tensor to the M32 chooser.

Three classes of information flow through this module, all derived from
measured observations; none bypass SHA256d or claim a hash-rate advantage:

1. ``face_bias`` (0–31): which 32-face nonce partition the trajectory
   prediction's Fisher information maximum maps to.  The chooser uses this
   to bias its candidate-window prefix ordering, not to invent new nonces.

2. ``LucasLadderStatus``: algebraic-family and collapse/resonance state of
   the declared Lucas ladder ``(10, 12, 15, 18, 20)``, derived
   from nonce-delta arithmetic over the M32 candidate window.  Deliberately
   decoupled from hardware energy measurements: it is pure arithmetic over
   the declared allocation contract.

3. ``causal_throttle``: True when TOE reports a high-entropy / low-coherence
   state (von Neumann entropy above ``_ENTROPY_THROTTLE`` or density-matrix
   purity below ``_COHERENCE_FLOOR``).  The chooser propagates this as
   ``SearchDecision.throttle = True``, halting new dispatch until coherence
   recovers — the cybernetic self-healing loop (Pillar 3).

Evidence boundary (Pillar 4 invariant):
  ``TOECausalSignal.is_valid()`` returns False for any torn state. The chooser
  checks this gate before acting on the signal and falls back to the standard
  exhaustive work contract when it fails.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence, Tuple

from lucas.ladder import FULL_LADDER

# Declared Lucas ladder — the five dimension indices into the Lucas sequence.
# These are topology anchors, not hash-rate predictions.
LUCAS_LADDER: Tuple[int, ...] = tuple(FULL_LADDER)

PHI = (1.0 + math.sqrt(5.0)) / 2.0
_L15 = 1364  # Lucas(15)
_DELTA = abs(PHI**15 - _L15)  # ≈ 7.33e-4; irrational Weyl rotation on T^n

_ENTROPY_THROTTLE = 3.5  # nats — above this the search state is diffuse
_COHERENCE_FLOOR = 0.10  # purity Tr(ρ²) — below this the state is torn
_FISHER_FLOOR = 0.5  # Fisher information — below this no intervention is optimal
_COLLAPSE_UNIQUE_MODS = 2  # ≤ this many distinct mod values → periodic limit cycle

# ---------------------------------------------------------------------------
# Consensus boundary (Pillar 4 hardening)
# ---------------------------------------------------------------------------
#
# A TOECausalSignal is feed-forward evidence only: it may steer work ordering
# and gate dispatch, but it may never reach the double-SHA256 / target
# comparison. Two mechanisms enforce that:
#
# 1. ``_assert_no_consensus_fields`` — build_toe_signal recursively rejects any
#    TOE result carrying consensus-domain keys (fail-closed: the signal is
#    never produced rather than sanitised).
#
# 2. ``boundary_token`` — every signal self-attests a SHA-256 token bound to
#    its feed-forward payload under a domain-separated tag. ``is_valid()``
#    requires the token to match, so a torn or tampered signal is rejected by
#    the chooser/coordinator gates.

_FORBIDDEN_CONSENSUS_KEYS = frozenset(
    {
        "target",
        "bits",
        "nonce",
        "header",
        "block_header",
        "share",
        "difficulty",
        "sha256",
        "sha256d",
        "pow",
        "proof",
        "merkle_root",
        "block_hash",
        "extranonce",
        "extranonce2",
        "coinbase",
        "ntime",
        "submission",
        "candidate",
        "valid_hash",
        "share_valid",
        "pool_accepted",
        "block_confirmed",
    }
)

_BOUNDARY_DOMAIN_TAG = "pythia.toe-signal.consensus-boundary.v1"


class TOEConsensusBoundaryError(ValueError):
    """A TOE result attempted to carry consensus-domain material."""


def _assert_no_consensus_fields(node: Any, path: str = "result") -> None:
    """Fail-closed assertion: TOE output must not carry consensus keys.

    Recursively walks mappings/sequences and raises
    ``TOEConsensusBoundaryError`` on the first key whose normalised name is a
    consensus-domain term (target, nonce, header, sha256d, ...). The signal is
    refused rather than filtered — a TOE output that reaches for consensus
    vocabulary is a boundary violation, not a shape to repair.
    """
    if isinstance(node, Mapping):
        for key, value in node.items():
            normalized = str(key).strip().lower()
            if normalized in _FORBIDDEN_CONSENSUS_KEYS:
                raise TOEConsensusBoundaryError(
                    f"TOE output carries consensus-domain key {path}.{normalized}"
                )
            _assert_no_consensus_fields(value, f"{path}.{normalized}")
    elif isinstance(node, (list, tuple)):
        for index, item in enumerate(node):
            _assert_no_consensus_fields(item, f"{path}[{index}]")


# ---------------------------------------------------------------------------
# Lucas arithmetic helpers — no external dependency
# ---------------------------------------------------------------------------


def _lucas(n: int) -> int:
    """Lucas number L_n (L_0 = 2, L_1 = 1)."""
    if n == 0:
        return 2
    if n == 1:
        return 1
    a, b = 2, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b


# ---------------------------------------------------------------------------
# LucasLadderStatus
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LucasLadderStatus:
    """Algebraic-family state across the declared Lucas ladder.

    Attributes
    ----------
    ladder_idx : int
        Index 0–4 into ``LUCAS_LADDER``.
    ladder_value : int
        ``LUCAS_LADDER[ladder_idx]``.
    resonant : bool
        True when the nonce-delta stream fits the golden-ratio irrational
        rotation within ``5 %`` of ``ladder_value`` — the dense-coverage
        regime described in AGENTS.md §1.3.
    collapse_detected : bool
        True when the stream has collapsed into a periodic limit cycle
        (≤ ``_COLLAPSE_UNIQUE_MODS`` distinct modular residues across ≥ 4
        samples), meaning the δ drift has been lost and the search is trapped.
    family : str
        Always ``"golden"`` for Lucas/Fibonacci indices; extended to
        ``"plastic"`` / ``"supergolden"`` / ``"tribonacci"`` when the
        algebraic-family substrate (``turing_core``) is available.
    residual : float
        Mean absolute deviation of actual nonce-delta modular residues from
        the golden-walk prediction.  Lower is better.
    audit_note : str
        Human-readable classifier label.  Never used as a validity claim.
    """

    ladder_idx: int
    ladder_value: int
    resonant: bool
    collapse_detected: bool
    family: str
    residual: float
    audit_note: str


# ---------------------------------------------------------------------------
# TOECausalSignal
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TOECausalSignal:
    """Immutable feed-forward signal from the TOE tensor to the M32 chooser.

    The chooser reads this object but must not modify it or the candidate
    window it was derived from.  Any alteration to the declared work contract
    goes through ``MiningIntelligenceChooser.choose()``.
    """

    # Face geometry hint
    face_bias: int = 0
    face_confidence: float = 0.0

    # Algebraic family status — set after candidate window is known
    ladder: LucasLadderStatus | None = None

    # Throttle gate — high entropy or low coherence halts new dispatch
    causal_throttle: bool = False

    # Trajectory observables (audit only — do not drive SHA256d)
    trend: str = "stable"
    trend_rate: float = 0.0
    intervention_optimal: bool = False

    # Tomography observables (audit only)
    coherence: float = 0.0
    energy: float = 0.0
    entropy: float = 0.0

    # Provenance
    job_id: str = ""
    node_id: int = 0
    sequence: int = 0

    # Consensus-boundary attestation — stamped at construction by
    # __post_init__; covers every feed-forward field EXCEPT ``ladder`` (the
    # coordinator attaches ladder post-hoc from the declared candidate
    # window, so dataclasses.replace(ladder=...) must not invalidate it).
    boundary_token: str = ""

    def __post_init__(self) -> None:
        if not self.boundary_token:
            object.__setattr__(self, "boundary_token", self.boundary_attestation())

    def _boundary_payload(self) -> bytes:
        canonical = json.dumps(
            {
                "face_bias": self.face_bias,
                "face_confidence": self.face_confidence,
                "causal_throttle": self.causal_throttle,
                "trend": self.trend,
                "trend_rate": self.trend_rate,
                "intervention_optimal": self.intervention_optimal,
                "coherence": self.coherence,
                "energy": self.energy,
                "entropy": self.entropy,
                "job_id": self.job_id,
                "node_id": self.node_id,
                "sequence": self.sequence,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return (_BOUNDARY_DOMAIN_TAG + "|" + canonical).encode("utf-8")

    def boundary_attestation(self) -> str:
        """Domain-separated SHA-256 attestation bound to the signal payload."""
        return "TOE-BND-" + hashlib.sha256(self._boundary_payload()).hexdigest()

    def is_valid(self) -> bool:
        """Minimum validity gate (Pillar 4 fail-closed invariant).

        Returns False for any torn state: coherence below floor, face out of
        range, negative entropy, or a boundary attestation token that does
        not match the signal payload.  The chooser falls back to the
        standard exhaustive contract when this gate fails.
        """
        return (
            self.coherence >= _COHERENCE_FLOOR
            and 0 <= self.face_bias < 32
            and self.entropy >= 0.0
            and isinstance(self.boundary_token, str)
            and hmac.compare_digest(self.boundary_token, self.boundary_attestation())
        )


# ---------------------------------------------------------------------------
# lucas_ladder_status
# ---------------------------------------------------------------------------


def lucas_ladder_status(candidate_window: Sequence[int]) -> LucasLadderStatus:
    """Detect algebraic family and collapse/resonance in the candidate nonce stream.

    Algorithm
    ---------
    1. Compute consecutive nonce deltas from the declared M32 window.
    2. For each ladder index k, compute L_k = Lucas(k) and the predicted
       modular residues under the irrational golden walk
       ``(L_k * δ * (j+1)) mod L_k``.
    3. Choose the ladder index with the smallest mean absolute deviation
       (best fit).
    4. Flag *collapse* when ≤ ``_COLLAPSE_UNIQUE_MODS`` distinct modular
       residues appear across ≥ 4 deltas (periodic limit cycle).
    5. Flag *resonance* when the residual is < 5 % of the ladder value
       and no collapse is detected (dense irrational coverage regime).

    This is pure arithmetic over the declared allocation contract.  No
    hardware observable is consumed and no SHA256d advantage is claimed.
    The candidate window itself is never mutated.
    """
    if not candidate_window:
        return LucasLadderStatus(
            ladder_idx=0,
            ladder_value=LUCAS_LADDER[0],
            resonant=False,
            collapse_detected=False,
            family="unknown",
            residual=float("inf"),
            audit_note="empty_window",
        )

    deltas = [
        abs(candidate_window[i + 1] - candidate_window[i])
        for i in range(min(len(candidate_window) - 1, 31))
    ]

    if not deltas:
        return LucasLadderStatus(
            ladder_idx=0,
            ladder_value=LUCAS_LADDER[0],
            resonant=False,
            collapse_detected=False,
            family="golden",
            residual=0.0,
            audit_note="single_candidate",
        )

    best_idx = 0
    best_residual = float("inf")

    for i, k in enumerate(LUCAS_LADDER):
        l_k = _lucas(k)
        predicted = [(l_k * _DELTA * (j + 1)) % l_k for j in range(len(deltas))]
        residual = sum(abs((d % l_k) - p) for d, p in zip(deltas, predicted)) / len(deltas)
        if residual < best_residual:
            best_residual = residual
            best_idx = i

    best_value = LUCAS_LADDER[best_idx]
    mods = [(d % best_value) for d in deltas]
    collapse = len(set(mods)) <= _COLLAPSE_UNIQUE_MODS and len(mods) >= 4
    resonant = (best_residual < best_value * 0.05) and not collapse

    return LucasLadderStatus(
        ladder_idx=best_idx,
        ladder_value=best_value,
        resonant=resonant,
        collapse_detected=collapse,
        family="golden",
        residual=best_residual,
        audit_note="resonant" if resonant else "collapsed" if collapse else "divergent",
    )


# ---------------------------------------------------------------------------
# build_toe_signal
# ---------------------------------------------------------------------------


def build_toe_signal(context: Any) -> TOECausalSignal:
    """Convert a measured ``TOEMiningContext`` into a feed-forward causal signal.

    Every field is derived from the observed ``context.result``; no domain
    state is invented.  The ``ladder`` field is left ``None`` here because
    the candidate window is not available until the coordinator materialises
    it; the coordinator calls ``lucas_ladder_status`` and uses
    ``dataclasses.replace`` to attach the result before passing the signal
    to the chooser.

    Raises ``ValueError`` if ``context`` has no ``result`` mapping.
    """
    result: Mapping[str, Any] = context.result
    if not isinstance(result, Mapping):
        raise ValueError("TOEMiningContext.result must be a Mapping")

    # Consensus boundary: refuse to build a signal from any TOE output that
    # reaches for consensus vocabulary. TOE never enters the target path.
    _assert_no_consensus_fields(result)

    tomo: Mapping[str, Any] = result.get("state_tomography") or {}
    traj: Mapping[str, Any] = result.get("trajectory_prediction") or {}

    coherence = float(tomo.get("coherence", 0.0))
    entropy = float(tomo.get("entropy", 0.0))
    energy = float(tomo.get("energy", 0.0))

    causal_throttle = entropy > _ENTROPY_THROTTLE or coherence < _COHERENCE_FLOOR

    # Face bias: Fisher-maximum intervention point → modular projection onto 0–31
    face_bias = 0
    face_confidence = 0.0
    intervention_optimal = False
    for pt in traj.get("intervention_points") or []:
        fisher = float(pt.get("fisher_info", 0.0))
        if fisher >= _FISHER_FLOOR and fisher > face_confidence:
            t = float(pt.get("time", 0.0))
            face_bias = int(t * 10) % 32
            face_confidence = min(fisher / 4.0, 1.0)
            intervention_optimal = bool(pt.get("is_optimal", False))

    return TOECausalSignal(
        face_bias=face_bias,
        face_confidence=face_confidence,
        ladder=None,
        causal_throttle=causal_throttle,
        trend=str(traj.get("trend", "stable")),
        trend_rate=float(traj.get("trend_rate", 0.0)),
        intervention_optimal=intervention_optimal,
        coherence=coherence,
        energy=energy,
        entropy=entropy,
        job_id=str(context.job_id),
        node_id=int(context.node_id),
        sequence=int(context.sequence),
    )


# Public aliases for constants imported by chronus.mla1517.mining.__init__
FISHER_FLOOR = _FISHER_FLOOR
STALENESS_SECONDS = 8  # seconds after which a cached TOE context is considered stale

__all__ = [
    "LUCAS_LADDER",
    "FISHER_FLOOR",
    "STALENESS_SECONDS",
    "LucasLadderStatus",
    "TOECausalSignal",
    "TOEConsensusBoundaryError",
    "lucas_ladder_status",
    "build_toe_signal",
]

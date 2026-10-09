"""Chronus — Consortium Push Protocol.

The governance layer for the consortium fabric: institutions ratchet the
``PadFabric`` forward one honest, cross-checked, owned, monotone push at
a time. First principles throughout — no framework imports, no
simulators, no mocks:

- a MEASURED push must carry a sha256 receipt bound to the claim's
  identity (``measurement_evidence``/``verify_receipt`` recompute the
  digest from the proposal fields, so a receipt cannot be copied from
  another proposal);
- a FORMULATION push must carry a first-principles derivation, and the
  gate rejects any derivation that imports a quantum framework
  (:func:`is_first_principles` enforces the no-framework boundary);
- a THEORETICAL push must carry a quantitative, falsifiable prediction;
- cross-check requires 2+ peer institutions, never the proposer;
- ownership is exclusive: one institution owns a metric;
- the fabric never shrinks: pushes are monotone and a stale
  ``from_value`` fails closed;
- every verdict lands in an append-only, hash-chained ledger that any
  party can re-verify.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .m5_ultra import PadFabric, consortium_fabric


class TruthClass(str, Enum):
    MEASURED = "measured"          # requires evidence receipt
    FORMULATION = "formulation"    # requires first-principles derivation
    THEORETICAL = "theoretical"    # requires falsifiable prediction


class Axis(str, Enum):
    INGEST = "ingest"              # CERN
    FABRICATION = "fabrication"    # MIT
    PHOTONICS = "photonics"        # Caltech, Cambridge
    MATERIALS = "materials"        # Princeton
    SYSTEMS = "systems"            # Stanford
    COHERENCE = "coherence"        # Oxford


class PushVerdict(str, Enum):
    ADMITTED = "admitted"
    REJECTED_NO_EVIDENCE = "rejected_no_evidence"
    REJECTED_NO_DERIVATION = "rejected_no_derivation"
    REJECTED_UNFALSIFIABLE = "rejected_unfalsifiable"
    REJECTED_NO_CROSSCHECK = "rejected_no_crosscheck"
    REJECTED_OWNERSHIP_CONFLICT = "rejected_ownership_conflict"
    REJECTED_REGRESSION = "rejected_regression"


#: The seven consortium institutions. Shared pads are not an institution
#: and cannot propose or verify.
CONSORTIUM_INSTITUTIONS: Tuple[str, ...] = (
    "CERN", "MIT", "Caltech", "Princeton", "Stanford", "Oxford", "Cambridge",
)

_INSTITUTION_CANONICAL = {name.upper(): name for name in CONSORTIUM_INSTITUTIONS}

#: Exclusive metric ownership. No two institutions own the same metric.
OWNERSHIP: Dict[str, str] = {
    "cern_wlcg.capacity_bytes": "CERN",
    "pad.qubits_per_pad": "MIT",
    "interconnect.edge_bandwidth": "Caltech",
    "qec.logical_error_rate": "Princeton",
    "totals.neural_engine_cores": "Stanford",
    "entanglement.edges": "Oxford",
    "totals.gpu_photonic_cores": "Cambridge",
}

#: Quantum frameworks and simulators are banned from first-principles
#: derivations. Identifier-boundary matching, case-insensitive.
_FRAMEWORK_TOKENS = (
    "qiskit", "cirq", "pennylane", "openqasm", "qasm", "pyquil",
    "projectq", "quipper", "qsharp", "braket", "stim", "qutip",
)
_FRAMEWORK_RE = re.compile(
    r"(?<![A-Za-z0-9_])(" + "|".join(_FRAMEWORK_TOKENS) + r")(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
_NUMERIC_RE = re.compile(r"\d")
_RECEIPT_RE = re.compile(r"^sha256:([0-9a-f]{64})$")


def canonical_institution(name: str) -> str:
    """Normalize an institution name ('CALTECH' -> 'Caltech')."""
    return _INSTITUTION_CANONICAL.get(str(name).strip().upper(), "")


def owner_of(metric: str) -> Optional[str]:
    return OWNERSHIP.get(metric)


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PushProposal:
    institution: str
    axis: Axis
    metric: str
    from_value: Optional[float]
    to_value: float
    truth_class: TruthClass
    verifiers: Tuple[str, ...]
    timestamp: float
    evidence: Optional[str] = None      # sha256 receipt if MEASURED
    derivation: Optional[str] = None    # first-principles proof if FORMULATION
    prediction: Optional[str] = None    # falsifiable claim if THEORETICAL

    def canonical(self) -> Dict[str, Any]:
        return {
            "institution": self.institution,
            "axis": str(self.axis.value if isinstance(self.axis, Axis) else self.axis),
            "metric": self.metric,
            "from_value": self.from_value,
            "to_value": self.to_value,
            "truth_class": str(
                self.truth_class.value
                if isinstance(self.truth_class, TruthClass)
                else self.truth_class
            ),
            "evidence": self.evidence,
            "derivation": self.derivation,
            "prediction": self.prediction,
            "verifiers": list(self.verifiers),
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class PushReceipt:
    proposal: PushProposal
    verdict: PushVerdict
    ledger_row: str = ""               # assigned by append(); hash-chained
    timestamp: float = 0.0


def _serialize(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _receipt_payload(receipt: PushReceipt) -> Dict[str, Any]:
    return {
        "proposal": receipt.proposal.canonical(),
        "verdict": receipt.verdict.value,
        "timestamp": receipt.timestamp,
    }


# ---------------------------------------------------------------------------
# Measured-evidence receipts (bound to the claim's identity)
# ---------------------------------------------------------------------------

def measurement_evidence(
    institution: str,
    metric: str,
    from_value: Optional[float],
    to_value: float,
) -> str:
    """Produce the sha256 receipt a MEASURED push must carry.

    The digest binds (institution, metric, from_value, to_value), so a
    receipt attests to one specific measured claim and verifies only
    against that claim.
    """
    blob = _serialize(
        {
            "institution": canonical_institution(institution) or institution,
            "metric": metric,
            "from_value": from_value,
            "to_value": to_value,
        }
    )
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def verify_receipt(evidence: str, proposal: PushProposal) -> bool:
    """Recompute the bound digest and compare. No receipt, no admission."""
    if not evidence or not isinstance(evidence, str):
        return False
    match = _RECEIPT_RE.match(evidence.strip())
    if match is None:
        return False
    expected = measurement_evidence(
        proposal.institution,
        proposal.metric,
        proposal.from_value,
        proposal.to_value,
    )
    return evidence.strip() == expected


# ---------------------------------------------------------------------------
# First-principles and falsifiability predicates
# ---------------------------------------------------------------------------

def is_first_principles(derivation: Optional[str]) -> bool:
    """A derivation must exist, be substantive, and import no quantum
    framework or simulator — the qiskit/cirq boundary, enforced here."""
    if not derivation or not str(derivation).strip():
        return False
    return _FRAMEWORK_RE.search(str(derivation)) is None


def is_falsifiable(prediction: Optional[str]) -> bool:
    """A falsifiable claim carries a measurable quantity that can fail."""
    if not prediction or not str(prediction).strip():
        return False
    return _NUMERIC_RE.search(str(prediction)) is not None


# ---------------------------------------------------------------------------
# Metric resolution over the fabric
# ---------------------------------------------------------------------------

def _uniform_pad_field(fabric: PadFabric, field_name: str) -> Optional[float]:
    """Read a per-pad spec field only when every pad agrees."""
    values = {getattr(p.spec, field_name) for p in fabric.pads}
    if len(values) != 1:
        return None
    (value,) = values
    return float(value)


def _uniform_link_bandwidth(fabric: PadFabric) -> Optional[float]:
    rates = {
        link.bandwidth_bytes_per_second
        for link in fabric.links
        if link.bandwidth_bytes_per_second is not None
    }
    if len(rates) != 1:
        return None
    (rate,) = rates
    return float(rate)


def read_metric(fabric: PadFabric, metric: str) -> Optional[float]:
    """Resolve a metric name against the fabric.

    ``None`` means the metric does not exist on this fabric; the
    monotonicity gate treats absent metrics as a 0.0 baseline so the
    first push of a new metric can be admitted honestly.
    """
    key = str(metric).strip()
    head, _, rest = key.partition(".")

    if head == "totals":
        return _optional_float(fabric.as_dict()["totals"].get(rest))
    if head == "pad":
        field_name = {
            "qubits_per_pad": "log2_hilbert_dim",
        }.get(rest, rest)
        return _uniform_pad_field(fabric, field_name)
    if head == "interconnect":
        if rest == "aggregate_bps":
            return float(fabric.interconnect_bandwidth_bps)
        if rest == "edge_bandwidth":
            return _uniform_link_bandwidth(fabric)
        if rest == "edges":
            return float(fabric.n_links)
        return None
    if head == "quantum":
        return _optional_float(fabric.quantum_block().get(rest))

    for tier in fabric.memory_tiers:
        if tier.name == head:
            if rest == "capacity_bytes":
                return _optional_float(tier.total_capacity_bytes)
            if rest == "bandwidth_bytes_per_second":
                return _optional_float(tier.bandwidth_bytes_per_second)
            if rest == "units":
                return float(tier.units)
            return None
    for channel in fabric.channels:
        if channel.name == head:
            if rest == "bandwidth_bytes_per_second":
                return _optional_float(channel.bandwidth_bytes_per_second)
            return None
    if rest == "edges":
        return float(fabric.links_by_kind.get(head, 0))
    return None


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


# ---------------------------------------------------------------------------
# Pushable fabric view — the mutable metric state pushes act on
# ---------------------------------------------------------------------------

@dataclass
class PushableFabric:
    """Mutable metric view over an immutable PadFabric.

    The source fabric is never mutated: admitted pushes write metric
    overrides here, recompute the elevation summary, and append their
    receipts to this view's evidence. ``truth_class`` tracks the most
    recent admitted push — a MEASURED push promotes the view to
    measured status.
    """

    fabric: PadFabric
    overrides: Dict[str, float] = field(default_factory=dict)
    evidence: List[PushReceipt] = field(default_factory=list)
    truth_class: str = ""
    elevation: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.truth_class:
            self.truth_class = self.fabric.truth_class
        self.recompute_elevation()

    @classmethod
    def from_fabric(cls, fabric: PadFabric) -> "PushableFabric":
        return cls(fabric=fabric)

    def read(self, metric: str) -> Optional[float]:
        if metric in self.overrides:
            return self.overrides[metric]
        return read_metric(self.fabric, metric)

    def write(self, metric: str, value: float) -> None:
        self.overrides[metric] = float(value)
        self.recompute_elevation()

    def recompute_elevation(self) -> None:
        """Refresh derived elevation values from current metric state."""
        qubits = self.read("pad.qubits_per_pad")
        hilbert_log2 = (
            qubits * self.fabric.n_registers if qubits is not None else None
        )
        aggregate = read_metric(self.fabric, "interconnect.aggregate_bps")
        channel_bps = {
            ch.name: self.read(f"{ch.name}.bandwidth_bytes_per_second")
            for ch in self.fabric.channels
        }
        self.elevation = {
            "n_pads": self.fabric.n_pads,
            "n_links": self.fabric.n_links,
            "hilbert_log2_dim": hilbert_log2,
            "aggregate_bandwidth_bytes_per_second": aggregate,
            "channel_bandwidths": channel_bps,
            "entanglement_edges": self.read("entanglement.edges"),
            "totals_neural_engine_cores": self.read("totals.neural_engine_cores"),
            "totals_gpu_photonic_cores": self.read("totals.gpu_photonic_cores"),
            "truth_class": self.truth_class,
        }


# ---------------------------------------------------------------------------
# Gates — run in order; first failure wins
# ---------------------------------------------------------------------------

def passes_truth_gate(p: PushProposal) -> PushVerdict:
    if p.truth_class == TruthClass.MEASURED:
        if not p.evidence or not verify_receipt(p.evidence, p):
            return PushVerdict.REJECTED_NO_EVIDENCE
    elif p.truth_class == TruthClass.FORMULATION:
        if not p.derivation or not is_first_principles(p.derivation):
            return PushVerdict.REJECTED_NO_DERIVATION
    elif p.truth_class == TruthClass.THEORETICAL:
        if not p.prediction or not is_falsifiable(p.prediction):
            return PushVerdict.REJECTED_UNFALSIFIABLE
    else:
        return PushVerdict.REJECTED_NO_EVIDENCE
    return PushVerdict.ADMITTED


def passes_crosscheck(p: PushProposal) -> PushVerdict:
    """2+ verifiers, none the proposer, all known consortium institutions."""
    proposer = canonical_institution(p.institution) or str(p.institution).strip()
    seen: set[str] = set()
    for v in p.verifiers:
        canon = canonical_institution(v)
        if not canon or canon == proposer or canon in seen:
            continue
        seen.add(canon)
    if len(seen) < 2:
        return PushVerdict.REJECTED_NO_CROSSCHECK
    return PushVerdict.ADMITTED


def passes_ownership(p: PushProposal) -> PushVerdict:
    owner = owner_of(p.metric)
    if owner is not None and owner != (
        canonical_institution(p.institution) or p.institution
    ):
        return PushVerdict.REJECTED_OWNERSHIP_CONFLICT
    return PushVerdict.ADMITTED


def passes_monotonicity(p: PushProposal, fabric: PushableFabric) -> PushVerdict:
    """The fabric never shrinks; a stale from_value fails closed."""
    current = fabric.read(p.metric)
    baseline = 0.0 if current is None else float(current)
    if p.to_value < baseline:
        return PushVerdict.REJECTED_REGRESSION
    declared = p.from_value if p.from_value is not None else baseline
    if float(declared) != baseline:
        return PushVerdict.REJECTED_REGRESSION
    return PushVerdict.ADMITTED


# ---------------------------------------------------------------------------
# Admit / apply
# ---------------------------------------------------------------------------

def _make_receipt(p: PushProposal, verdict: PushVerdict) -> PushReceipt:
    return PushReceipt(proposal=p, verdict=verdict, timestamp=p.timestamp)


def admit(p: PushProposal, fabric: PushableFabric) -> PushReceipt:
    for gate in (passes_truth_gate, passes_crosscheck, passes_ownership):
        verdict = gate(p)
        if verdict != PushVerdict.ADMITTED:
            return _make_receipt(p, verdict)
    verdict = passes_monotonicity(p, fabric)
    if verdict != PushVerdict.ADMITTED:
        return _make_receipt(p, verdict)
    apply_push(p, fabric)
    return _make_receipt(p, PushVerdict.ADMITTED)


def apply_push(p: PushProposal, fabric: PushableFabric) -> None:
    fabric.write(p.metric, p.to_value)
    fabric.truth_class = p.truth_class.value
    fabric.elevation["truth_class"] = fabric.truth_class


# ---------------------------------------------------------------------------
# Append-only hash-chained ledger
# ---------------------------------------------------------------------------

LEDGER_GENESIS = hashlib.sha256(
    b"chronus.consortium_push:genesis"
).hexdigest()


@dataclass
class PushLedger:
    rows: List[PushReceipt] = field(default_factory=list)
    head: str = LEDGER_GENESIS
    genesis: str = LEDGER_GENESIS

    def as_dict(self) -> Dict[str, Any]:
        return {
            "genesis": self.genesis,
            "head": self.head,
            "rows": [
                {
                    **_receipt_payload(r),
                    "ledger_row": r.ledger_row,
                }
                for r in self.rows
            ],
        }


def append(ledger: PushLedger, receipt: PushReceipt) -> PushLedger:
    """Append a receipt; its row hash chains on the previous head."""
    row = hashlib.sha256(
        ledger.head.encode("utf-8") + _serialize(_receipt_payload(receipt))
    ).hexdigest()
    ledger.rows.append(replace(receipt, ledger_row=row))
    ledger.head = row
    return ledger


def verify_ledger(ledger: PushLedger) -> bool:
    head = ledger.genesis
    for r in ledger.rows:
        expected = hashlib.sha256(
            head.encode("utf-8") + _serialize(_receipt_payload(r))
        ).hexdigest()
        if r.ledger_row != expected:
            return False
        head = r.ledger_row
    return head == ledger.head


def push_cycle(
    fabric: PushableFabric,
    proposals: List[PushProposal],
    ledger: PushLedger,
) -> PushLedger:
    """Deterministic order: proposals sorted by timestamp."""
    for p in sorted(proposals, key=lambda x: float(x.timestamp)):
        append(ledger, admit(p, fabric))
    return ledger


# ---------------------------------------------------------------------------
# Diagnosis and invariants
# ---------------------------------------------------------------------------

_DIAGNOSES = {
    PushVerdict.REJECTED_NO_EVIDENCE: "MEASURED claim missing receipt",
    PushVerdict.REJECTED_NO_DERIVATION: "FORMULATION claim missing first-principles derivation",
    PushVerdict.REJECTED_UNFALSIFIABLE: "THEORETICAL claim not falsifiable",
    PushVerdict.REJECTED_NO_CROSSCHECK: "fewer than 2 peer verifiers",
    PushVerdict.REJECTED_OWNERSHIP_CONFLICT: "metric owned by another institution",
    PushVerdict.REJECTED_REGRESSION: "proposed value below current fabric state",
    PushVerdict.ADMITTED: "admitted",
}


def diagnose(receipt: PushReceipt) -> str:
    return _DIAGNOSES.get(receipt.verdict, "admitted")


def verify_invariants(ledger: PushLedger) -> Dict[str, bool]:
    """Check the protocol invariants that live on the ledger itself.

    monotonicity and exclusivity are enforced at the gates; append_only,
    truth_honesty and no_framework_import are auditable over receipts.
    """
    append_only = verify_ledger(ledger)
    truth_honesty = True
    no_framework = True
    for r in ledger.rows:
        if r.verdict != PushVerdict.ADMITTED:
            continue
        p = r.proposal
        if p.truth_class == TruthClass.MEASURED and not p.evidence:
            truth_honesty = False
        if p.truth_class == TruthClass.FORMULATION and not p.derivation:
            truth_honesty = False
        if p.truth_class == TruthClass.THEORETICAL and not p.prediction:
            truth_honesty = False
        if p.derivation and _FRAMEWORK_RE.search(p.derivation):
            no_framework = False
    return {
        "append_only": append_only,
        "truth_honesty": truth_honesty,
        "no_framework_import": no_framework,
    }


__all__ = [
    "Axis",
    "CONSORTIUM_INSTITUTIONS",
    "LEDGER_GENESIS",
    "OWNERSHIP",
    "PushLedger",
    "PushProposal",
    "PushReceipt",
    "PushVerdict",
    "PushableFabric",
    "TruthClass",
    "admit",
    "append",
    "apply_push",
    "canonical_institution",
    "diagnose",
    "is_falsifiable",
    "is_first_principles",
    "measurement_evidence",
    "owner_of",
    "passes_crosscheck",
    "passes_monotonicity",
    "passes_ownership",
    "passes_truth_gate",
    "push_cycle",
    "read_metric",
    "verify_invariants",
    "verify_ledger",
    "verify_receipt",
]

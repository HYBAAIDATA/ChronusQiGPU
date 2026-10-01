"""L-HRAS domain types — the explicit inputs and outputs of every operator.

Every field has a declared type. Where the blueprint names a shape that
the substrates do not own, it lives here. Nothing in this module performs
I/O or hides behaviour; these are records with derived views only.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from fractions import Fraction
from typing import Any, Mapping, Optional


def canonical_json(value: Any) -> str:
    """Deterministic JSON encoding used for digests, signatures and folds."""

    def _convert(v: Any) -> Any:
        if isinstance(v, Fraction):
            return {"fraction": [v.numerator, v.denominator]}
        if isinstance(v, bytes):
            return {"bytes": v.hex()}
        if isinstance(v, (set, frozenset)):
            return sorted(_convert(x) for x in v)
        if isinstance(v, Mapping):
            return {str(k): _convert(val) for k, val in v.items()}
        if isinstance(v, (list, tuple)):
            return [_convert(x) for x in v]
        if hasattr(v, "to_dict"):
            return _convert(v.to_dict())
        return v

    return json.dumps(_convert(value), sort_keys=True, separators=(",", ":"))


def digest_of(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class AdversaryClass(str, Enum):
    APT = "apt"
    INSIDER = "insider"
    SCRIPT_KIDDIE = "script_kiddie"
    BOTNET = "botnet"
    STATE_ACTOR = "state_actor"
    BENIGN = "benign"
    UNKNOWN = "unknown"


class RequestKind(str, Enum):
    BENIGN = "benign"
    ADVERSARIAL = "adversarial"


class AnomalyClass(str, Enum):
    NOMINAL = "nominal"
    SUSPICIOUS = "suspicious"
    ANOMALOUS = "anomalous"
    COMPROMISED = "compromised"


class Escalation(str, Enum):
    NONE = "none"
    OPEN_TICKET = "open_ticket"
    NOTIFY_SOC = "notify_soc"
    PAGE_ONCALL = "page_oncall"


ESCALATION_MEDIUM = 0.2
ESCALATION_HIGH = 0.5
ESCALATION_CRITICAL = 0.8

DECISION_ACTIONS = ("block", "redirect", "entangle", "monitor", "ignore")


# ---------------------------------------------------------------------------
# Preconditions — threat model, trust root, policy bundle
# ---------------------------------------------------------------------------


@dataclass
class ThreatModel:
    """Declared adversary universe. ``capabilities`` must cover every
    declared adversary; ``responses`` must cover every ATT&CK technique
    (threat_model_well_formed, Part IV)."""

    adversaries: list[str]
    capabilities: dict[str, list[str]]
    attck_techniques: list[str]
    responses: dict[str, list[str]]
    cost_map: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "adversaries": list(self.adversaries),
            "capabilities": {k: list(v) for k, v in self.capabilities.items()},
            "attck_techniques": list(self.attck_techniques),
            "responses": {k: list(v) for k, v in self.responses.items()},
            "cost_map": dict(self.cost_map),
        }


@dataclass
class TrustRoot:
    """Root of trust for request and attestation verification (TR1–TR2).

    Holds an HMAC secret. Verification is closed: an absent or wrong
    signature fails. The secret itself never leaves this object.
    """

    key_id: str
    secret: bytes

    def sign(self, payload: Any) -> str:
        return hmac.new(
            self.secret, canonical_json(payload).encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def verify(self, token: str, payload: Any) -> bool:
        if not token:
            return False
        expected = self.sign(payload)
        return hmac.compare_digest(token, expected)


@dataclass
class RequestAttestation:
    """A signed claim of authenticity attached to a request."""

    token: str
    payload_digest: str
    issuer: str = "edge"
    issued_at: float = field(default_factory=time.time)

    def verify(self, trust_root: TrustRoot) -> bool:
        return trust_root.verify(self.token, {"digest": self.payload_digest})


@dataclass
class PolicyRule:
    effect: str  # "allow" | "deny"
    kind: Optional[str] = None
    scope: Optional[str] = None
    action: Optional[str] = None
    adversary_class: Optional[str] = None

    def matches(self, request: "Request") -> bool:
        if self.kind is not None and request.kind.value != self.kind:
            return False
        if self.scope is not None and request.scope != self.scope:
            return False
        if self.action is not None and request.action != self.action:
            return False
        if (
            self.adversary_class is not None
            and request.adversary_class.value != self.adversary_class
        ):
            return False
        return True


@dataclass
class PolicyBundle:
    """Signed policy set (PB1–PB2). ``signature`` covers the canonical
    rules; ``signatures_verified`` is set after checking against the
    trust root, not assumed."""

    version: str
    rules: list[PolicyRule] = field(default_factory=list)
    throttle_modes: dict[str, dict[str, Any]] = field(default_factory=dict)
    compliance_mappings: dict[str, list[str]] = field(default_factory=dict)
    signature: Optional[str] = None
    signatures_verified: bool = False
    default_allow: bool = True

    def sign_with(self, trust_root: TrustRoot) -> None:
        self.signature = trust_root.sign(self.signing_payload())

    def signing_payload(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "rules": [{k: v for k, v in vars(r).items() if v is not None} for r in self.rules],
            "throttle_modes": dict(self.throttle_modes),
            "compliance_mappings": dict(self.compliance_mappings),
            "default_allow": self.default_allow,
        }

    def verify_signature(self, trust_root: TrustRoot) -> bool:
        if not self.signature:
            self.signatures_verified = False
            return False
        self.signatures_verified = trust_root.verify(self.signature, self.signing_payload())
        return self.signatures_verified

    def compliance_mappings_valid(self) -> bool:
        return all(
            isinstance(controls, list) and bool(controls)
            for controls in self.compliance_mappings.values()
        )

    def subset(self, tenant_id: str) -> "PolicyBundle":
        scoped = [r for r in self.rules if r.scope is None or r.scope in (tenant_id, "global")]
        return PolicyBundle(
            version=f"{self.version}/{tenant_id}",
            rules=scoped,
            throttle_modes=dict(self.throttle_modes),
            compliance_mappings=dict(self.compliance_mappings),
            signature=self.signature,
            signatures_verified=self.signatures_verified,
            default_allow=self.default_allow,
        )


@dataclass
class Contact:
    name: str
    channel: str
    target: str


@dataclass
class BreakGlassPolicy:
    allowed_actors: list[str]
    allowed_reasons: list[str]
    duration_seconds: float = 900.0

    def allows(self, actor: str, reason: str) -> bool:
        return actor in self.allowed_actors and (
            "*" in self.allowed_reasons or reason in self.allowed_reasons
        )


@dataclass
class SSOConfig:
    """SSO provider descriptor. ``issuer`` names the trust boundary;
    ``secret`` verifies HMAC-issued tokens; ``open`` providers accept
    externally-asserted identities only when flagged."""

    issuer: str
    secret: bytes = b""
    open: bool = False

    def verify(self, token: str) -> bool:
        if not token:
            return False
        if self.open:
            return True
        if not self.secret:
            return False
        parts = token.rsplit(".", 1)
        if len(parts) != 2:
            return False
        subject, sig = parts
        expected = hmac.new(self.secret, subject.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected)

    def issue(self, subject: str) -> str:
        sig = hmac.new(self.secret, subject.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{subject}.{sig}"


@dataclass
class AlertChannelSpec:
    kind: str  # slack | email | pager | webhook
    target: str


# ---------------------------------------------------------------------------
# Requests, responses, and every operator's declared output
# ---------------------------------------------------------------------------


@dataclass
class Distribution:
    """A measured distribution — never asserted (OP5)."""

    mean: float
    stddev: float
    samples: int
    p50: float
    p95: float
    p99: float

    def to_dict(self) -> dict[str, Any]:
        return vars(self)


@dataclass
class Request:
    """A request presented to the Guardian.

    ``state`` is the request's density matrix (list of complex-pair
    encoded as nested float lists) used by the purity/entropy gates.
    ``position``/``target`` are manifold coordinates for the Yang–Mills
    and Poincaré evaluators.
    """

    kind: RequestKind
    attestation: RequestAttestation
    actor: str = "anonymous"
    action: str = "read"
    resource: str = "default"
    scope: str = "global"
    payload: Any = b""
    telemetry: list[float] = field(default_factory=list)
    state: list[list[float]] = field(default_factory=lambda: [[1.0]])
    position: tuple[float, float] = (0.0, 0.0)
    target: tuple[float, float] = (0.0, 0.0)
    adversary_class: AdversaryClass = AdversaryClass.BENIGN
    adversary_id: Optional[str] = None
    attack_vector: list[float] = field(default_factory=list)
    observation: dict[str, float] = field(default_factory=dict)

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "actor": self.actor,
            "action": self.action,
            "resource": self.resource,
            "scope": self.scope,
            "payload": self.payload,
            "telemetry": list(self.telemetry),
            "state": self.state,
            "position": list(self.position),
            "target": list(self.target),
            "adversary_class": self.adversary_class.value,
            "adversary_id": self.adversary_id,
            "attack_vector": list(self.attack_vector),
            "observation": dict(self.observation),
        }

    def payload_digest(self) -> str:
        return digest_of(self.canonical_payload())


def signed_request(trust_root: TrustRoot, request: Request, issuer: str = "edge") -> Request:
    """Attach a trust-root attestation to a request (test + edge helper)."""
    request.attestation = RequestAttestation(
        token=trust_root.sign({"digest": request.payload_digest()}),
        payload_digest=request.payload_digest(),
        issuer=issuer,
    )
    return request


@dataclass
class Attestation:
    """One signed attestation node (AC1–AC3)."""

    id: str
    event: str
    payload: Any
    digest: str
    signature: str
    issued_at: float = field(default_factory=time.time)
    substrate: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event": self.event,
            "payload": self.payload,
            "digest": self.digest,
            "signature": self.signature,
            "issued_at": self.issued_at,
            "substrate": dict(self.substrate),
        }


@dataclass
class CompositeAttestation:
    chain: list[Attestation]
    root: Attestation
    policy: str
    k: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain": [a.to_dict() for a in self.chain],
            "root": self.root.to_dict(),
            "policy": self.policy,
            "k": self.k,
        }


@dataclass
class AnomalyReport:
    fidelity: Distribution
    divergence: float
    classification: AnomalyClass
    attestation: Optional[Attestation] = None


@dataclass
class Prediction:
    """Distribution over threat level — a measured forecast."""

    distribution: Distribution
    threat_level: float
    features: dict[str, float] = field(default_factory=dict)


@dataclass
class CounterfactualPath:
    steps: list[str]
    likelihood: float
    adversary: Optional[str]
    expected_target: str = "generic"
    next_action_distribution: dict[str, float] = field(default_factory=dict)


@dataclass
class Multiplication:
    vectors: list[Any]
    combined: Any
    cardinality: int
    digest: str
    attestation: Attestation
    ok: bool = True


@dataclass
class EntangledIntelligence:
    states: dict[str, Any]
    entanglement: Any
    correlations: dict[str, Any]
    attestation: Attestation
    verified: bool = True


@dataclass
class WorkerResponse:
    guardian_id: str
    ok: bool
    vote: str
    digest: str


@dataclass
class Decision:
    choice: str
    votes: dict[str, Any]
    threshold: Fraction


@dataclass
class Defense:
    swarm: Any
    responses: list[WorkerResponse]
    decision: Decision
    attestation: Attestation
    paths: list[CounterfactualPath] = field(default_factory=list)
    ok: bool = True


@dataclass
class Trap:
    trigger: str
    effect: str


@dataclass
class Decoy:
    appearance: str
    substance: Trap


@dataclass
class HoneyPot:
    id: str
    decoy: Decoy
    path: CounterfactualPath
    trap: Trap
    appearance: str
    substance: Trap
    attestation: Attestation


@dataclass
class AdversaryBelief:
    state: list[list[float]]  # 2x2 density matrix
    prior: Optional[str] = None


@dataclass
class InfoOp:
    kind: str  # confuse | mislead | delay | expose
    target: Optional[str]


@dataclass
class Exposure:
    adversary: Optional[str]
    before: AdversaryBelief
    after: AdversaryBelief
    kl: float
    attestation: Attestation


@dataclass
class ThrottleDecision:
    mode: dict[str, Any]
    reason: str
    scope: str
    started_at: float
    expires_at: float
    blast_radius: float
    attestation: Optional[Attestation] = None


@dataclass
class Adversary:
    id: str
    first_seen: float
    last_seen: float
    events: list[Request] = field(default_factory=list)
    attribution: set[str] = field(default_factory=set)

    def update(self, event: Request) -> None:
        self.events.append(event)
        self.last_seen = time.time()


@dataclass
class AdversaryProfile:
    id: str
    first_seen: float
    last_seen: float
    event_count: int
    tactics: list[str]
    techniques: list[str]
    attribution: set[str]
    persistence: float
    lateral_score: float
    escalation_score: float


@dataclass
class ManifoldRegion:
    center: tuple[float, float]
    radius: float
    homotopy: str
    ok: bool = True


@dataclass
class EffortRatio:
    verification_cost: int
    adversary_cost: int
    ratio: Fraction
    declared: Fraction
    ok: bool = True


@dataclass
class GaugeField:
    mass_gap: float
    boundary: dict[str, Any]
    field_action: Any = None
    ok: bool = True


@dataclass
class SignalDistribution:
    adversary_class: AdversaryClass
    distribution: Distribution
    critical_line: float
    ok: bool = True


@dataclass
class RankBound:
    adversary_class: AdversaryClass
    reachable_rank: int
    bound: int
    ok: bool = True


@dataclass
class HodgeClass:
    name: str
    weight: float = 0.0


@dataclass
class FlowState:
    velocity: float
    viscosity: float
    horizon: float
    norm: float
    lyapunov: float = 0.0
    ok: bool = True


@dataclass
class TopologicalSignature:
    manifold: str
    region: str
    homotopy: str
    lyapunov: float
    greene: float
    action_var: float
    period1: bool


@dataclass
class CurvatureReport:
    point: tuple[float, float]
    ricci: float
    scalar: float
    sectional: float
    geodesic_dist: float


@dataclass
class Certificate:
    masks: list[int]
    digest: str
    lucas: list[int]
    depth: int
    attestation: Optional[Attestation] = None
    token: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "masks": list(self.masks),
            "digest": self.digest,
            "lucas": list(self.lucas),
            "depth": self.depth,
            "token": self.token,
        }


@dataclass
class Response:
    allowed: bool
    reason: str
    attestation: Optional[CompositeAttestation] = None
    defense: Optional[Defense] = None
    exposure: Optional[Exposure] = None
    throttle: Optional[ThrottleDecision] = None
    prediction: Optional[Prediction] = None
    paths: list[CounterfactualPath] = field(default_factory=list)
    anomaly: Optional[AnomalyReport] = None
    adversary: Optional[Adversary] = None
    profile: Optional[AdversaryProfile] = None
    escalate: Escalation = Escalation.NONE


@dataclass
class JointState:
    """The six-intelligence joint state entangled in F4 (Part VIII)."""

    projection: dict[str, Any]
    entanglement: dict[str, Any]
    correlations: dict[str, Any]
    predictor: Any = None
    causal_graph: Any = None
    adversary_beliefs: dict[str, AdversaryBelief] = field(default_factory=dict)
    adversaries: dict[str, Adversary] = field(default_factory=dict)
    baseline_distribution: dict[str, Distribution] = field(default_factory=dict)
    ti_cache: list[Any] = field(default_factory=list)


@dataclass
class StandingState:
    multiply: bool
    entangle: bool
    swarm: bool
    honey_pot: bool
    willow_expose: bool
    topologies: dict[str, bool]
    predictor: Any
    causal_graph: Any
    monitor: Any
    sentry: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "multiply": self.multiply,
            "entangle": self.entangle,
            "swarm": self.swarm,
            "honey_pot": self.honey_pot,
            "willow_expose": self.willow_expose,
            "topologies": dict(self.topologies),
        }

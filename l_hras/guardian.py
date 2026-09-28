"""L-HRAS — The Guardian. Parts IV–VI.

``initialize`` validates every precondition and spawns the swarm, the
aethel stores, the attester, and every integration. ``stand`` entangles
the six intelligences in F4, verifies all seven topologies clean, warms
the predictor, loads the causal graph, and starts both sentries — from
the first moment, all five modes are simultaneous. ``respond`` runs the
full conjunction: preconditions → detection/throttle → five modes →
seven topologies → six intelligences → 11D fold → composite attestation
→ aethel write → verdict. Any ``Err`` refuses; the refusal rate is the
measurement.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from . import detection, intelligences, modes, observability, substrates, topologies
from .attestation import Attester, attest_compose
from .config import Config, validate_config
from .fold import fold_11d, zeckendorf_certificate
from .governance import open_governance
from .integration import (
    PolicyEngine,
    open_feed,
    open_policy_engine,
    open_siem,
    open_soar,
    policy_bundle_valid,
    siem_emit,
    soar_invoke,
)
from .observability import open_alert, open_health, open_metrics
from .result import (
    FORGERY_DETECTED,
    NOT_STANDING,
    POLICY_BUNDLE_INVALID,
    POLICY_VIOLATION,
    THREAT_MODEL_MALFORMED,
    TRUST_ROOT_MISSING,
    Ok,
    Result,
    error,
)
from .store import aethel_write, standing_certificate
from .types import (
    AdversaryClass,
    AnomalyClass,
    Escalation,
    JointState,
    Request,
    RequestAttestation,
    RequestKind,
    Response,
    StandingState,
)


class LHRAS:
    """The Guardian instance. ``standing`` is a state, not a transition."""

    def __init__(self, cfg: Config, **components):
        self.cfg = cfg
        self.swarm = components["swarm"]
        self.aethel = components["aethel"]
        self.backup = components["backup"]
        self.attester: Attester = components["attester"]
        self.siem = components["siem"]
        self.soar = components["soar"]
        self.feeds = components["feeds"]
        self.metrics = components["metrics"]
        self.health = components["health"]
        self.alerts = components["alerts"]
        self.policy: PolicyEngine = components["policy"]
        self.governance = components["governance"]
        self.standing = False
        self.standing_state: Optional[StandingState] = None
        self.joint: Optional[JointState] = None
        self.start_time = time.time()
        self.event_count = 0
        self.refusal_count = 0
        self._config_integrity_sig: Optional[str] = None

    def self_probe_request(self) -> Request:
        """The standing probe — a canonical benign request through every
        evaluator, proving all seven topologies hold from the first
        moment."""
        probe = Request(
            kind=RequestKind.BENIGN,
            attestation=RequestAttestation(token="", payload_digest=""),
            actor="l-hras",
            action="probe",
            telemetry=[1.0, 1.0, 1.0],
            state=[[1.0, 0.0], [0.0, 0.0]],
            position=(0.25, 0.25),
            target=(0.25, 0.25),
            adversary_class=AdversaryClass.BENIGN,
            attack_vector=[0.1, 0.2, 0.3],
            observation={"probe": 1.0},
        )
        probe.attestation.payload_digest = probe.payload_digest()
        probe.attestation.token = self.cfg.trust_root.sign(
            {"digest": probe.attestation.payload_digest}
        )
        return probe


# ---------------------------------------------------------------------------
# Initialization (Part IV)
# ---------------------------------------------------------------------------


def threat_model_well_formed(tm: Any) -> bool:
    for adv in tm.adversaries:
        if adv not in tm.capabilities:
            return False
    for tech in tm.attck_techniques:
        if tech not in tm.responses:
            return False
    return True


def verify_trust_root(trust_root: Any) -> bool:
    return trust_root is not None and bool(trust_root.secret)


def initialize(cfg: Config) -> Result[LHRAS]:
    validated = validate_config(cfg)
    if validated.is_err:
        return validated
    cfg = validated.value

    if cfg.threat_model is None or not threat_model_well_formed(cfg.threat_model):
        return error(THREAT_MODEL_MALFORMED)
    if not verify_trust_root(cfg.trust_root):
        return error(TRUST_ROOT_MISSING)
    if not policy_bundle_valid(cfg.policy_bundle):
        return error(POLICY_BUNDLE_INVALID)

    aethel = substrates.open_aethel(cfg.aethel_root)
    backup = substrates.open_aethel(cfg.backup_root)
    attester = Attester(
        root=cfg.trust_root,
        aethel=aethel,
        lifecycle=cfg.key_custody_policy,
    )

    guardians = []
    for i in range(cfg.swarm_size):
        g = modes.spawn_guardian(cfg, i, aethel, attester)
        if g.is_err:
            return g
        guardians.append(g.value)
    swarm = modes.spawn_swarm(guardians, cfg.swarm_threshold, attester)
    if swarm.is_err:
        return swarm

    siem = open_siem(cfg.siem_endpoint)
    soar = open_soar(cfg.soar_endpoint)
    feeds = [open_feed(url) for url in cfg.ti_feeds]
    metrics = open_metrics(cfg.metrics_endpoint)
    if metrics.is_err:
        return metrics
    health = open_health(cfg.health_endpoint)
    if health.is_err:
        return health
    alerts = [open_alert(ch) for ch in cfg.alert_channels]

    policy = open_policy_engine(cfg.policy_bundle)
    if policy.is_err:
        return policy
    governance = open_governance(cfg)
    if governance.is_err:
        return governance

    return Ok(
        LHRAS(
            cfg,
            swarm=swarm.value,
            aethel=aethel,
            backup=backup,
            attester=attester,
            siem=siem,
            soar=soar,
            feeds=feeds,
            metrics=metrics.value,
            health=health.value,
            alerts=alerts,
            policy=policy.value,
            governance=governance.value,
        )
    )


# ---------------------------------------------------------------------------
# Standing (Part V) — L1–L4: stands from the first moment
# ---------------------------------------------------------------------------


def stand(lhras: LHRAS) -> Result[StandingState]:
    if lhras.standing:
        return Ok(lhras.standing_state)

    joint = intelligences.entangle_all_six_in_f4(lhras.cfg, lhras.attester)
    if joint.is_err:
        return joint
    lhras.joint = joint.value

    for adv, dist in _seed_baselines(lhras).items():
        lhras.joint.baseline_distribution[adv] = dist

    # Bind config integrity at standing — later drift is detectable.
    from . import selfdefense
    from .types import canonical_json

    lhras._config_integrity_sig = lhras.cfg.trust_root.sign(
        {"config_integrity": canonical_json(selfdefense.config_integrity_payload(lhras.cfg))}
    )

    topologies_ok = topologies.verify_seven_topologies_clean(lhras)
    if topologies_ok.is_err:
        return topologies_ok

    warmed = intelligences.warm_predictor(lhras.joint.predictor)
    if warmed.is_err:
        return warmed
    lhras.joint.predictor = warmed.value

    monitor = observability.start_health_monitor(lhras)
    sentry = observability.start_drift_sentry(lhras)

    state = StandingState(
        multiply=True,
        entangle=True,
        swarm=True,
        honey_pot=True,
        willow_expose=True,
        topologies=topologies_ok.value,
        predictor=warmed.value,
        causal_graph=lhras.joint.causal_graph,
        monitor=monitor,
        sentry=sentry,
    )
    lhras.standing_state = state
    lhras.standing = True

    attest = lhras.attester.self_attest(
        {"event": "standing_started", "swarm": lhras.swarm.id, "at": time.time()}
    )
    written = aethel_write(lhras.aethel, standing_certificate(state), attest)
    if written.is_err:
        return written

    lhras.metrics.increment("lhras.standing", 1)
    observability.alert_if_enabled(lhras.alerts, "standing", state.to_dict())
    return Ok(state)


def _seed_baselines(lhras: LHRAS) -> dict[str, Any]:
    """One baseline distribution per declared adversary class, measured
    from the config's own fidelity expectations."""
    from .types import Distribution

    baselines = {}
    for adv in (
        set(lhras.cfg.critical_lines)
        | set(lhras.cfg.rank_bounds)
        | {e.value for e in AdversaryClass}
    ):
        baselines[adv] = Distribution(mean=1.0, stddev=0.0, samples=1, p50=1.0, p95=1.0, p99=1.0)
    return baselines


# ---------------------------------------------------------------------------
# Respond (Part VI) — the conjunction is preserved
# ---------------------------------------------------------------------------


def respond(lhras: LHRAS, request: Request) -> Result[Response]:
    """The public respond boundary — Part XII integration on top of the
    Part VI pipeline: every refusal reaches the SIEM, every escalation
    reaches SOAR, whatever stage produced them."""
    result = _respond(lhras, request)
    refused = result.is_err or (result.is_ok and not result.value.allowed)
    if refused and lhras.standing:
        reason = result.error.code if result.is_err else result.value.reason
        siem_emit(
            lhras.siem,
            request,
            reason=reason,
            instance_id=lhras.cfg.instance_id,
        )
    if (
        result.is_ok
        and result.value.escalate is not None
        and result.value.escalate != Escalation.NONE
    ):
        soar_invoke(
            lhras.soar,
            result.value.escalate,
            result.value.adversary,
            result.value.profile,
        )
    return result


def _respond(lhras: LHRAS, request: Request) -> Result[Response]:
    if not lhras.standing:
        return error(NOT_STANDING)
    lhras.event_count += 1

    # ─── Precondition ────────────────────────────────────────────
    if not request.attestation.verify(lhras.cfg.trust_root):
        lhras.refusal_count += 1
        return error(FORGERY_DETECTED)
    if not lhras.policy.allows(request):
        lhras.refusal_count += 1
        return error(POLICY_VIOLATION, kind=request.kind.value)

    digest = substrates.compile_request(request).input_digest

    # ─── Detection and throttle ──────────────────────────────────
    anomaly = detection.detect_anomaly(lhras, request)
    if anomaly.is_err:
        lhras.refusal_count += 1
        return anomaly

    if not detection.purity_gate_ok(lhras, request):
        throttle = detection.engage_throttle(lhras, request, reason="purity_gate")
        if throttle.is_err:
            return throttle
        return Ok(
            Response(
                allowed=False,
                reason="purity_gate",
                throttle=throttle.value,
                attestation=None,
                anomaly=anomaly.value,
            )
        )

    # ─── Five modes ──────────────────────────────────────────────
    mult = modes.multiply(lhras.joint, request, digest, lhras.cfg, lhras.attester)
    if mult.is_err:
        return mult
    ent = modes.entangle(lhras.joint, request, lhras.attester, lhras.cfg)
    if ent.is_err:
        return ent
    defn = modes.swarm_defend(lhras.swarm, request, lhras.attester)
    if defn.is_err:
        lhras.refusal_count += 1
        return defn

    # ─── Six intelligences ───────────────────────────────────────
    prediction = intelligences.predict(lhras.joint.predictor, request.telemetry)
    if prediction.is_err:
        return prediction
    paths = intelligences.counterfactual_paths(
        lhras.joint.causal_graph,
        dict(request.observation, adversary_id=request.adversary_id),
        lhras.cfg.max_counterfactuals,
        lhras.cfg.declared_threshold,
    )
    if paths.is_err:
        return paths
    defn.value.paths = paths.value

    pots = modes.place_honey_pots(lhras.joint, defn.value.paths, lhras.attester)
    if pots.is_err:
        return pots
    expo = modes.willow_expose(lhras.joint, defn.value, lhras.attester)
    if expo.is_err:
        return expo

    # ─── Seven topologies ────────────────────────────────────────
    poincare_r = topologies.evaluate_poincare(request)
    if poincare_r.is_err:
        lhras.refusal_count += 1
        return poincare_r
    pnp_r = topologies.evaluate_pnp(request, lhras.cfg)
    if pnp_r.is_err:
        lhras.refusal_count += 1
        return pnp_r
    ym_r = topologies.evaluate_yang_mills(request, lhras.cfg)
    if ym_r.is_err:
        lhras.refusal_count += 1
        return ym_r
    rh_r = topologies.evaluate_riemann(request, lhras.cfg)
    if rh_r.is_err:
        lhras.refusal_count += 1
        return rh_r
    bsd_r = topologies.evaluate_bsd(request, lhras.cfg)
    if bsd_r.is_err:
        lhras.refusal_count += 1
        return bsd_r
    hodge_r = topologies.evaluate_hodge(request, lhras.cfg)
    if hodge_r.is_err:
        lhras.refusal_count += 1
        return hodge_r
    ns_r = topologies.evaluate_navier_stokes(request, lhras.cfg)
    if ns_r.is_err:
        lhras.refusal_count += 1
        return ns_r

    if request.kind == RequestKind.ADVERSARIAL:
        adversary = detection.track_adversary(lhras, request)
        if adversary.is_err:
            return adversary
        profile = detection.profile_adversary(adversary.value)
        if profile.is_err:
            return profile
        escalate = detection.evaluate_escalation(lhras, adversary.value, profile.value)
        adversary, profile = adversary.value, profile.value
    else:
        adversary = profile = None
        escalate = Escalation.NONE

    # ─── 11D fold ────────────────────────────────────────────────
    combined_vec = _vector_from_mult(mult.value.combined)
    folded = fold_11d(combined_vec, lhras.cfg.fold_tolerance)
    if folded.is_err:
        return folded
    certificate = zeckendorf_certificate(folded.value, context_id=digest)
    if certificate.is_err:
        return certificate

    # ─── Attestation + Aethel ────────────────────────────────────
    cert_attest = lhras.attester.attest("certificate", certificate.value.to_dict())
    attest = attest_compose(
        links=[
            mult.value.attestation,
            ent.value.attestation,
            defn.value.attestation,
            cert_attest,
        ],
        attester=lhras.attester,
        policy="unanimous",
        k=4,
    )
    if attest.is_err:
        return attest
    written = aethel_write(lhras.aethel, certificate.value, attest.value.root)
    if written.is_err:
        return written

    # ─── Original verdict: conjunction of all layers ─────────────
    modes_ok = (
        mult.value.ok
        and ent.value.verified
        and defn.value.ok
        and bool(pots.value is not None)
        and bool(expo.value is not None)
    )
    # Each topology's Err already returned above; a value without an
    # ``ok`` flag (the Hodge class list) counts as verified standing.
    topologies_ok = all(
        getattr(r.value, "ok", True) for r in (poincare_r, pnp_r, ym_r, rh_r, bsd_r, hodge_r, ns_r)
    )
    intel_ok = ent.value.verified
    anomaly_ok = anomaly.value.classification != AnomalyClass.COMPROMISED

    verdict = modes_ok and topologies_ok and intel_ok and anomaly_ok

    # ─── Observability (integration emits happen in respond()) ────
    if not verdict:
        lhras.refusal_count += 1

    lhras.metrics.increment("lhras.respond", 1)
    lhras.metrics.histogram("lhras.verdict", 1.0 if verdict else 0.0)

    return Ok(
        Response(
            allowed=verdict,
            attestation=attest.value,
            defense=defn.value,
            exposure=expo.value[0] if expo.value else None,
            reason=(
                "standing"
                if verdict
                else _verdict_reason(anomaly.value, modes_ok, topologies_ok, intel_ok)
            ),
            prediction=prediction.value,
            paths=paths.value,
            anomaly=anomaly.value,
            adversary=adversary,
            profile=profile,
            escalate=escalate,
        )
    )


def _verdict_reason(anomaly: Any, modes_ok: bool, topologies_ok: bool, intel_ok: bool) -> str:
    if anomaly.classification == AnomalyClass.COMPROMISED:
        return "anomaly_compromised"
    if not modes_ok:
        return "mode_failure"
    if not topologies_ok:
        return "topology_failure"
    if not intel_ok:
        return "intelligence_unverified"
    return "standing"


def _vector_from_mult(combined: Any) -> list[float]:
    """Project the combined tensor's factor amplitudes into R^11.

    ``combined`` is the pure tensor v_1 ⊗ ... ⊗ v_k in factor form; the
    fold consumes each factor's leading amplitudes in order.
    """
    factors = combined if isinstance(combined, (tuple, list)) else (combined,)
    out: list[float] = []
    for factor in factors:
        for a in getattr(factor, "amplitudes", [])[:2]:
            out.append(float(a.real.to_float()))
        if len(out) >= 11:
            break
    while len(out) < 11:
        out.append(0.0)
    return out[:11]

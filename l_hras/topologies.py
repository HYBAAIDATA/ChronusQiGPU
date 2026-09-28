"""The seven topologies — Part IX.

Each is a computable operator with a declared contract:
    MATHEMATICAL OBJECT → OPERATOR → INPUTS → OUTPUTS → INVARIANT → TEST.
They do not prove the Millennium Problems; they stand on their
structures. Every evaluation is measured — a violated invariant is an
``Err``, never a silently recorded boolean.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from . import substrates
from .result import (
    BSD_RANK_EXCEEDED,
    HODGE_UNKNOWN_CLASS,
    NS_BLOW_UP,
    PNP_RATIO_VIOLATED,
    POINCARE_ISOLATION_FAILED,
    RIEMANN_BELOW_CRITICAL_LINE,
    YM_FIELD_BROKEN,
    Err,
    Ok,
    Result,
    error,
)
from .types import (
    EffortRatio,
    FlowState,
    GaugeField,
    HodgeClass,
    ManifoldRegion,
    RankBound,
    SignalDistribution,
)

TOPOLOGIES = ("poincare", "pnp", "yang_mills", "riemann", "bsd", "hodge", "navier_stokes")


# ---------------------------------------------------------------------------
# Poincaré — hyperbolic 3-manifold threat isolation
# ---------------------------------------------------------------------------


def evaluate_poincare(event: Any) -> Result[ManifoldRegion]:
    try:
        point = substrates.to_point(event.position)
        cls = substrates.manifold_classify(point)
    except Exception as exc:
        return error(POINCARE_ISOLATION_FAILED, reason=str(exc))
    return Ok(
        ManifoldRegion(
            center=point,
            radius=float(cls["radius"]),
            homotopy=str(cls["homotopy"]),
            ok=True,
        )
    )


# ---------------------------------------------------------------------------
# P vs NP — effort accounting: verification vs construction
# ---------------------------------------------------------------------------


def evaluate_pnp(event: Any, cfg: Any) -> Result[EffortRatio]:
    try:
        v = substrates.digest_cost(event)
    except Exception as exc:
        return error(PNP_RATIO_VIOLATED, reason=str(exc))
    a = cost_from_threat_model(event, cfg.threat_model)
    if a == 0:
        return error(PNP_RATIO_VIOLATED, reason="adversary_cost_zero")
    ratio = Fraction(v, a)
    if ratio > cfg.pnp_ratio:
        return error(
            PNP_RATIO_VIOLATED, ratio=str(ratio), declared=str(cfg.pnp_ratio)
        )
    return Ok(
        EffortRatio(
            verification_cost=int(v),
            adversary_cost=int(a),
            ratio=ratio,
            declared=cfg.pnp_ratio,
            ok=True,
        )
    )


def cost_from_threat_model(event: Any, threat_model: Any) -> int:
    """Declared adversary construction cost for the event's class."""
    if threat_model is None:
        return 0
    return int(threat_model.cost_map.get(event.adversary_class.value, 0))


# ---------------------------------------------------------------------------
# Yang–Mills — gauge confinement: escape_cost(d) ≥ mass_gap · d
# ---------------------------------------------------------------------------


def evaluate_yang_mills(event: Any, cfg: Any) -> Result[GaugeField]:
    if cfg.mass_gap is None or cfg.mass_gap <= 0:
        # A non-positive mass gap is a broken gauge field — fails closed.
        return error(YM_FIELD_BROKEN, mass_gap=cfg.mass_gap)
    try:
        d = substrates.distance(event.position, event.target)
        lyap = substrates.lyapunov_at(substrates.to_point(event.position))
    except Exception as exc:
        return error(YM_FIELD_BROKEN, reason=str(exc))
    cost = lyap * cfg.mass_gap * d
    if cost < cfg.mass_gap * d:
        return error(
            YM_FIELD_BROKEN, cost=cost, mass_gap=cfg.mass_gap, distance=d
        )
    return Ok(
        GaugeField(
            mass_gap=cfg.mass_gap,
            boundary=substrates.boundary(),
            field_action=lambda adv, p, t: substrates.lyapunov_at(
                substrates.to_point(p)
            )
            * substrates.distance(p, t),
            ok=True,
        )
    )


# ---------------------------------------------------------------------------
# Riemann — critical-line detection on the signal distribution
# ---------------------------------------------------------------------------


def evaluate_riemann(event: Any, cfg: Any) -> Result[SignalDistribution]:
    adv = event.adversary_class.value
    if adv not in cfg.critical_lines:
        return error(RIEMANN_BELOW_CRITICAL_LINE, reason=f"no_critical_line:{adv}")
    line = cfg.critical_lines[adv]
    try:
        dist = substrates.fidelity_kernel(event.adversary_class, event)
    except Exception as exc:
        return error(RIEMANN_BELOW_CRITICAL_LINE, reason=str(exc))
    if dist.mean <= line:
        return error(
            RIEMANN_BELOW_CRITICAL_LINE, mean=dist.mean, critical_line=line
        )
    return Ok(
        SignalDistribution(
            adversary_class=event.adversary_class,
            distribution=dist,
            critical_line=line,
            ok=True,
        )
    )


# ---------------------------------------------------------------------------
# BSD — Mordell–Weil rank-bounded reach on the 32-frame
# ---------------------------------------------------------------------------


def evaluate_bsd(event: Any, cfg: Any) -> Result[RankBound]:
    adv = event.adversary_class.value
    if adv not in cfg.rank_bounds:
        return error(BSD_RANK_EXCEEDED, reason=f"no_rank_bound:{adv}")
    bound = int(cfg.rank_bounds[adv])
    try:
        state3d = _adversary_state3d(event)
        r = substrates.reachable_faces(state3d)
    except Exception as exc:
        return error(BSD_RANK_EXCEEDED, reason=str(exc))
    if r > bound:
        return error(BSD_RANK_EXCEEDED, rank=r, bound=bound)
    return Ok(
        RankBound(
            adversary_class=event.adversary_class,
            reachable_rank=int(r),
            bound=bound,
            ok=True,
        )
    )


def _adversary_state3d(event: Any) -> tuple[float, float, float]:
    """Deterministic adversary projection onto the 32-frame: hashed id
    seeds three coordinates inside the unit cube."""
    import hashlib

    seed = event.adversary_id or event.adversary_class.value
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return (
        digest[0] / 255.0,
        digest[1] / 255.0,
        digest[2] / 255.0,
    )


# ---------------------------------------------------------------------------
# Hodge — cohomological decomposition of the attack vector
# ---------------------------------------------------------------------------


def evaluate_hodge(event: Any, cfg: Any) -> Result[list[HodgeClass]]:
    try:
        classes = substrates.decompose_attack(event.attack_vector, cfg.hodge_basis)
    except Exception as exc:
        return error(HODGE_UNKNOWN_CLASS, reason=str(exc))
    declared = set(cfg.hodge_basis)
    for c in classes:
        if c.name not in declared:
            return error(HODGE_UNKNOWN_CLASS, hodge_class=c.name)
    return Ok(classes)


# ---------------------------------------------------------------------------
# Navier–Stokes — flow containment: Lyapunov ≤ viscosity
# ---------------------------------------------------------------------------


def evaluate_navier_stokes(event: Any, cfg: Any) -> Result[FlowState]:
    try:
        flow = substrates.predict_flow(event.attack_vector)
        lyap = substrates.flow_lyapunov(flow, event.attack_vector)
    except Exception as exc:
        return error(NS_BLOW_UP, reason=str(exc))
    if lyap > cfg.viscosity:
        return error(NS_BLOW_UP, lyapunov=lyap, viscosity=cfg.viscosity)
    return Ok(
        FlowState(
            velocity=float(getattr(flow, "trend_rate", 0.0)),
            viscosity=cfg.viscosity,
            horizon=float(getattr(flow, "time_horizon", 0.0)),
            norm=abs(float(getattr(flow, "forecast_6_step", 0.0))),
            lyapunov=float(lyap),
            ok=True,
        )
    )


# ---------------------------------------------------------------------------
# Standing self-probe — all seven must be clean before the Guardian stands.
# ---------------------------------------------------------------------------


def verify_seven_topologies_clean(lhras: Any) -> Result[dict[str, bool]]:
    probe = lhras.self_probe_request()
    checks = {
        "poincare": evaluate_poincare(probe),
        "pnp": evaluate_pnp(probe, lhras.cfg),
        "yang_mills": evaluate_yang_mills(probe, lhras.cfg),
        "riemann": evaluate_riemann(probe, lhras.cfg),
        "bsd": evaluate_bsd(probe, lhras.cfg),
        "hodge": evaluate_hodge(probe, lhras.cfg),
        "navier_stokes": evaluate_navier_stokes(probe, lhras.cfg),
    }
    for name, result in checks.items():
        if result.is_err:
            return Err(result.error)
    return Ok({name: True for name in checks})

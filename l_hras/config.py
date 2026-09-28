"""L-HRAS configuration schema and validation (Part III).

Every threshold has provenance (TP1): ``provenance`` must name the source
of each scalar threshold and of every per-class ``critical_lines`` /
``rank_bounds`` entry, or validation fails closed.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Optional

from .result import (
    CONFIG_INCOMPLETE,
    ENTROPY_THRESHOLD_INVALID,
    FOLD_TOLERANCE_NONPOSITIVE,
    MAX_CF_NONPOSITIVE,
    PNP_RATIO_OUT_OF_RANGE,
    PURITY_THRESHOLD_INVALID,
    SWARM_TOO_SMALL,
    THRESHOLD_PROVENANCE_MISSING,
    VISCOSITY_NONPOSITIVE,
    Ok,
    Result,
    error,
)
from .types import (
    AlertChannelSpec,
    BreakGlassPolicy,
    Contact,
    PolicyBundle,
    PolicyRule,
    SSOConfig,
    ThreatModel,
    TrustRoot,
)

# Required fields, per the blueprint's REQUIRED list.
REQUIRED = (
    "threat_model",
    "trust_root",
    "policy_bundle",
    "mass_gap",
    "critical_lines",
    "rank_bounds",
    "hodge_basis",
    "viscosity",
    "pnp_ratio",
    "aethel_root",
    "sso_provider",
)

# Scalar thresholds that must carry provenance (TP1).
PROVENANCED_SCALARS = (
    "mass_gap",
    "viscosity",
    "pnp_ratio",
    "entropy_threshold",
    "purity_threshold",
    "fidelity_threshold",
)


@dataclass
class Config:
    """The Guardian's configuration. Fields map 1:1 to CONFIG_SCHEMA."""

    # Preconditions
    threat_model: Optional[ThreatModel] = None
    trust_root: Optional[TrustRoot] = None
    policy_bundle: Optional[PolicyBundle] = None

    # Seven topology constants
    mass_gap: Optional[float] = None
    critical_lines: dict[str, float] = field(default_factory=dict)
    rank_bounds: dict[str, int] = field(default_factory=dict)
    hodge_basis: list[str] = field(default_factory=list)
    viscosity: Optional[float] = None
    pnp_ratio: Optional[Fraction] = None

    # Standing
    swarm_size: int = 3
    swarm_threshold: Fraction = Fraction(2, 3)
    max_counterfactuals: int = 10_000
    declared_threshold: float = 0.5
    fold_tolerance: float = 1e-14
    state_dim: int = 3

    # Detection
    entropy_threshold: float = 0.0
    purity_threshold: float = 0.0
    fidelity_threshold: float = 0.0

    # Storage
    aethel_root: Optional[str] = None
    backup_root: Optional[str] = None

    # Integration
    siem_endpoint: Optional[str] = None
    soar_endpoint: Optional[str] = None
    ti_feeds: list[str] = field(default_factory=list)
    sso_provider: Optional[SSOConfig] = None

    # Governance
    compliance_mappings: dict[str, list[str]] = field(default_factory=dict)
    escalation_contacts: list[Contact] = field(default_factory=list)
    break_glass_policy: Optional[BreakGlassPolicy] = None
    key_custody_policy: dict[str, Any] = field(default_factory=dict)

    # Observability
    metrics_endpoint: Optional[str] = None
    health_endpoint: Optional[str] = None
    alert_channels: list[AlertChannelSpec] = field(default_factory=list)

    # Throttle defaults
    default_throttle_factor: float = 0.5
    throttle_duration: float = 300.0

    # Provenance: {"mass_gap": "...", "critical_lines": {adv: "..."}, ...}
    provenance: dict[str, Any] = field(default_factory=dict)

    # Identity
    instance_id: str = "l-hras-0"


def validate_config(cfg: Config) -> Result[Config]:
    """Part III validate_config — every check is a declared invariant."""

    for name in REQUIRED:
        if getattr(cfg, name) is None:
            return error(CONFIG_INCOMPLETE, field=name)
        if name in ("critical_lines", "rank_bounds", "hodge_basis") and not getattr(
            cfg, name
        ):
            return error(CONFIG_INCOMPLETE, field=name)

    if cfg.swarm_size < 3:
        return error(SWARM_TOO_SMALL, swarm_size=cfg.swarm_size)
    if cfg.pnp_ratio is None or not (Fraction(0) < cfg.pnp_ratio <= Fraction(1)):
        return error(PNP_RATIO_OUT_OF_RANGE, pnp_ratio=str(cfg.pnp_ratio))
    if cfg.viscosity is None or cfg.viscosity <= 0:
        return error(VISCOSITY_NONPOSITIVE, viscosity=cfg.viscosity)
    if cfg.fold_tolerance <= 0:
        return error(FOLD_TOLERANCE_NONPOSITIVE, fold_tolerance=cfg.fold_tolerance)
    if cfg.max_counterfactuals <= 0:
        return error(MAX_CF_NONPOSITIVE, max_counterfactuals=cfg.max_counterfactuals)
    if cfg.purity_threshold > 1:
        return error(PURITY_THRESHOLD_INVALID, purity_threshold=cfg.purity_threshold)
    if cfg.entropy_threshold < 0:
        return error(
            ENTROPY_THRESHOLD_INVALID, entropy_threshold=cfg.entropy_threshold
        )

    # TP1 — every threshold has declared provenance.
    for name in PROVENANCED_SCALARS:
        if cfg.provenance.get(name) is None:
            return error(THRESHOLD_PROVENANCE_MISSING, threshold=name)
    for adv in cfg.critical_lines:
        adv_prov = cfg.provenance.get("critical_lines") or {}
        if adv_prov.get(adv) is None:
            return error(
                THRESHOLD_PROVENANCE_MISSING, threshold="critical_lines", adversary=adv
            )
    for adv in cfg.rank_bounds:
        adv_prov = cfg.provenance.get("rank_bounds") or {}
        if adv_prov.get(adv) is None:
            return error(
                THRESHOLD_PROVENANCE_MISSING, threshold="rank_bounds", adversary=adv
            )

    return Ok(cfg)


# ---------------------------------------------------------------------------
# TOML loader — `cp config.example.toml config.toml` deployment path.
# ---------------------------------------------------------------------------


def _fraction(value: Any) -> Optional[Fraction]:
    if value is None:
        return None
    if isinstance(value, Fraction):
        return value
    if isinstance(value, (int, float)):
        return Fraction(value).limit_denominator(10**9)
    if isinstance(value, str) and "/" in value:
        num, den = value.split("/", 1)
        return Fraction(int(num), int(den))
    return Fraction(str(value))


def _threat_model(raw: dict[str, Any] | None) -> Optional[ThreatModel]:
    if raw is None:
        return None
    return ThreatModel(
        adversaries=list(raw.get("adversaries", [])),
        capabilities={k: list(v) for k, v in raw.get("capabilities", {}).items()},
        attck_techniques=list(raw.get("attck_techniques", [])),
        responses={k: list(v) for k, v in raw.get("responses", {}).items()},
        cost_map={k: int(v) for k, v in raw.get("cost_map", {}).items()},
    )


def _policy_bundle(raw: dict[str, Any] | None) -> Optional[PolicyBundle]:
    if raw is None:
        return None
    rules = [
        PolicyRule(
            effect=str(r.get("effect", "allow")),
            kind=r.get("kind"),
            scope=r.get("scope"),
            action=r.get("action"),
            adversary_class=r.get("adversary_class"),
        )
        for r in raw.get("rules", [])
    ]
    bundle = PolicyBundle(
        version=str(raw.get("version", "")),
        rules=rules,
        throttle_modes=dict(raw.get("throttle_modes", {})),
        compliance_mappings={
            k: list(v) for k, v in raw.get("compliance_mappings", {}).items()
        },
        signature=raw.get("signature"),
        default_allow=bool(raw.get("default_allow", True)),
    )
    return bundle


def config_from_dict(raw: dict[str, Any]) -> Config:
    """Build a :class:`Config` from decoded TOML/dict data."""

    trust = raw.get("trust_root") or {}
    trust_root = None
    if trust.get("key_id") is not None:
        trust_root = TrustRoot(
            key_id=str(trust["key_id"]),
            secret=str(trust.get("secret", "")).encode("utf-8"),
        )

    bundle = _policy_bundle(raw.get("policy_bundle"))
    if bundle is not None and trust_root is not None:
        # An unsigned bundle is signed by the local trust root at load —
        # signatures_verified is only ever the result of verification.
        if not bundle.signature:
            bundle.sign_with(trust_root)
        bundle.verify_signature(trust_root)

    sso = raw.get("sso_provider") or {}
    sso_provider = None
    if sso.get("issuer") is not None:
        sso_provider = SSOConfig(
            issuer=str(sso["issuer"]),
            secret=str(sso.get("secret", "")).encode("utf-8"),
            open=bool(sso.get("open", False)),
        )

    bg = raw.get("break_glass_policy") or {}
    break_glass = None
    if bg:
        break_glass = BreakGlassPolicy(
            allowed_actors=list(bg.get("allowed_actors", [])),
            allowed_reasons=list(bg.get("allowed_reasons", [])),
            duration_seconds=float(bg.get("duration_seconds", 900.0)),
        )

    contacts = [
        Contact(
            name=str(c.get("name", "")),
            channel=str(c.get("channel", "")),
            target=str(c.get("target", "")),
        )
        for c in raw.get("escalation_contacts", [])
    ]
    alerts = [
        AlertChannelSpec(kind=str(a.get("kind", "webhook")), target=str(a.get("target", "")))
        for a in raw.get("alert_channels", [])
    ]

    swarm = raw.get("standing", {})
    return Config(
        threat_model=_threat_model(raw.get("threat_model")),
        trust_root=trust_root,
        policy_bundle=bundle,
        mass_gap=(
            None if raw.get("mass_gap") is None else float(raw["mass_gap"])
        ),
        critical_lines={
            str(k): float(v) for k, v in (raw.get("critical_lines") or {}).items()
        },
        rank_bounds={str(k): int(v) for k, v in (raw.get("rank_bounds") or {}).items()},
        hodge_basis=[str(x) for x in raw.get("hodge_basis", [])],
        viscosity=(None if raw.get("viscosity") is None else float(raw["viscosity"])),
        pnp_ratio=_fraction(raw.get("pnp_ratio")),
        swarm_size=int(swarm.get("swarm_size", raw.get("swarm_size", 3))),
        swarm_threshold=_fraction(swarm.get("swarm_threshold", "2/3"))
        or Fraction(2, 3),
        max_counterfactuals=int(
            swarm.get("max_counterfactuals", raw.get("max_counterfactuals", 10_000))
        ),
        declared_threshold=float(
            swarm.get("declared_threshold", raw.get("declared_threshold", 0.5))
        ),
        fold_tolerance=float(swarm.get("fold_tolerance", raw.get("fold_tolerance", 1e-14))),
        state_dim=int(swarm.get("state_dim", raw.get("state_dim", 3))),
        entropy_threshold=float(raw.get("entropy_threshold", 0.0)),
        purity_threshold=float(raw.get("purity_threshold", 0.0)),
        fidelity_threshold=float(raw.get("fidelity_threshold", 0.0)),
        aethel_root=raw.get("aethel_root"),
        backup_root=raw.get("backup_root"),
        siem_endpoint=raw.get("siem_endpoint") or None,
        soar_endpoint=raw.get("soar_endpoint") or None,
        ti_feeds=[str(u) for u in raw.get("ti_feeds", [])],
        sso_provider=sso_provider,
        compliance_mappings={
            k: list(v) for k, v in (raw.get("compliance_mappings") or {}).items()
        },
        escalation_contacts=contacts,
        break_glass_policy=break_glass,
        key_custody_policy=dict(raw.get("key_custody_policy", {})),
        metrics_endpoint=raw.get("metrics_endpoint") or None,
        health_endpoint=raw.get("health_endpoint") or None,
        alert_channels=alerts,
        default_throttle_factor=float(raw.get("default_throttle_factor", 0.5)),
        throttle_duration=float(raw.get("throttle_duration", 300.0)),
        provenance=dict(raw.get("provenance", {})),
        instance_id=str(raw.get("instance_id", "l-hras-0")),
    )


def load_config(path: str | Path) -> Result[Config]:
    """Load a TOML config file and validate it — fail closed on any Err."""
    try:
        with open(path, "rb") as handle:
            raw = tomllib.load(handle)
    except OSError as exc:
        return error(CONFIG_INCOMPLETE, field="path", detail=str(exc))
    except tomllib.TOMLDecodeError as exc:
        return error(CONFIG_INCOMPLETE, field="toml", detail=str(exc))
    return validate_config(config_from_dict(raw))

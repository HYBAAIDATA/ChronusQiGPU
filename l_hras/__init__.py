"""L-HRAS — The Guardian.

Layered Heuristic Resilient Adversarial Security. A first-principles
mathematical security architecture for HYBA enterprise: every operator
is a computable mathematical object with declared inputs, declared
outputs, an invariant, and a test. Nothing is asserted — everything is
measured, and every measurement can falsify.

    There is no door.
    There is no perimeter.
    There is no wall.
    There is no single perimeter whose compromise grants trust.

The frame:
    MATHEMATICAL OBJECT → COMPUTABLE OPERATOR → EXPLICIT INPUTS →
    EXPLICIT OUTPUTS → INVARIANT → TEST → MEASURED BEHAVIOUR

Layout (lift-ready — ``substrates.py`` is the only repo boundary):

    result.py        Result monad + the Part XIII error taxonomy
    types.py         explicit inputs/outputs of every operator
    config.py        CONFIG_SCHEMA + validate_config (Part III)
    substrates.py    every CONSUME: over kellogg/aethel/toe
    attestation.py   Attester, Merkle chain, attest_compose (Part XI)
    store.py         aethel_write + certificate builders (Part XI)
    fold.py          11D Klein→Poincaré fold + Zeckendorf cert (Part XI)
    intelligences.py the six intelligences entangled in F4 (Part VIII)
    modes.py         the five simultaneous modes + swarm (Part VII)
    topologies.py    the seven topologies (Part IX)
    detection.py     anomaly/throttle/adversary tracking (Part X)
    integration.py   SIEM/SOAR/TI/SSO/policy engine (Part XII)
    governance.py    compliance, break glass, audit log (Part XII)
    observability.py metrics/health/alerts/monitors (Part XII)
    selfdefense.py   code/config integrity, witness mode (Part XII)
    federation.py    federate/share_threat/tenant_isolate (Part XII)
    guardian.py      initialize/stand/respond (Parts IV–VI)
    claims.py        claims register + invariant catalog (Parts XIV–XV)
    run.py           python -m l_hras.run --config config.toml (Part XVII)
"""

from .config import Config, config_from_dict, load_config, validate_config
from .guardian import LHRAS, initialize, respond, stand
from .result import Err, LHRASError, Ok, Result
from .types import (
    AdversaryClass,
    BreakGlassPolicy,
    Contact,
    PolicyBundle,
    PolicyRule,
    Request,
    RequestAttestation,
    RequestKind,
    Response,
    SSOConfig,
    ThreatModel,
    TrustRoot,
    signed_request,
)

__version__ = "1.0.0"
__all__ = [
    "AdversaryClass",
    "BreakGlassPolicy",
    "Config",
    "Contact",
    "Err",
    "LHRAS",
    "LHRASError",
    "Ok",
    "PolicyBundle",
    "PolicyRule",
    "Request",
    "RequestAttestation",
    "RequestKind",
    "Response",
    "Result",
    "SSOConfig",
    "ThreatModel",
    "TrustRoot",
    "config_from_dict",
    "initialize",
    "load_config",
    "respond",
    "signed_request",
    "stand",
    "validate_config",
]

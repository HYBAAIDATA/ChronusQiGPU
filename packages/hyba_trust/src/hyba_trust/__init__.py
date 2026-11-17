"""hyba_trust: trust states, promotion authority and demotion cascade for derived knowledge.

Implements the v5 promotion/demotion design with its review fixes. See README.md
for the differences from the pseudocode and the limits of this implementation.
"""

from .fabric import (
    AppealRefused,
    CascadeManifest,
    IllegalTransition,
    NotAuthorized,
    ReviewPacket,
    ReviewTask,
    SelfApproval,
    StaleReviewPacket,
    TrustError,
    TrustFabric,
    UseCase,
    consolidate,
)
from .invariants import check as check_invariants
from .model import (
    LEGAL_TRANSITIONS,
    PROJECTION_WEIGHT,
    STATES,
    SYSTEM,
    Actor,
    Atom,
    RiskTier,
    Role,
    State,
)
from .projection import ContextManifest, project

__all__ = [
    "Actor", "AppealRefused", "Atom", "CascadeManifest", "ContextManifest", "IllegalTransition",
    "LEGAL_TRANSITIONS", "NotAuthorized", "PROJECTION_WEIGHT", "ReviewPacket", "ReviewTask", "RiskTier",
    "Role", "STATES", "SYSTEM", "SelfApproval", "StaleReviewPacket", "State", "TrustError", "TrustFabric",
    "UseCase", "check_invariants", "consolidate", "project",
]

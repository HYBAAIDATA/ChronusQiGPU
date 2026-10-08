"""PYTHIPhiMiner-local AL HARAS wiring to the canonical TOE bridge."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

# The guardian plane (``al_haras``), the TOE bridge evidence provider
# (``toe``) and the TUQC inner package live at repo level. When the control
# API is entered through ``python main.py`` only this directory lands on
# sys.path, so the mediation imports must make the repo layout explicit —
# otherwise the guardian silently binds to None and every privileged route
# answers a permanent, unsatisfiable 503.
_PY_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PY_DIR.parent.parent.parent
_TUQC_DIR = _REPO_ROOT / "turing_universal_quantum_computer"
for _path in (str(_REPO_ROOT), str(_PY_DIR), str(_TUQC_DIR)):
    if _path not in sys.path:
        sys.path.append(_path)

from al_haras.guardian import DEFAULT_ALLOWED_OPERATIONS
from al_haras.runtime import GuardianAPI, build_guardian
from al_haras.settings import ALHarasSettings

# Operations the PYTHIA control API mediates through the guardian on its
# privileged prefixes (path minus /api/v1/, slashes to dots). Without them the
# default policy set denies every mediated control route.
_PYTHIA_ALLOWED_OPERATIONS: frozenset[str] = DEFAULT_ALLOWED_OPERATIONS | frozenset(
    {
        "mining.elevate",
        "mining.escalate",
        "mining.lease",
        "mining.evidence",
        "mining.start",
        "mining.submit",
        "mining.stop",
        "mining.switch",
        "security.status",
        "security.subscribe",
        "tensor.capabilities",
        "tensor.execute",
    }
)


@lru_cache(maxsize=1)
def _toe_bridge():
    from toe.bridge import TOEBridge

    return TOEBridge()


def _toe_evidence(observation: Mapping[str, Any]) -> Mapping[str, Any]:
    bridge = _toe_bridge()
    result = bridge.predict(dict(observation))
    if not isinstance(result, Mapping) or not result.get("available", False):
        raise RuntimeError("TOE prediction unavailable")
    required = (
        "state_tomography",
        "trajectory_prediction",
        "causal_analysis",
        "causal_ladder",
        "exact_tensor",
    )
    unavailable = [
        name
        for name in required
        if not isinstance(result.get(name), Mapping) or not result[name].get("available", False)
    ]
    if unavailable:
        raise RuntimeError(f"TOE capabilities unavailable: {','.join(unavailable)}")
    execution = bridge.execution_evidence()
    if not isinstance(execution, Mapping):
        raise RuntimeError("TOE execution evidence unavailable")
    return {
        "schema_version": "pythia.toe.guardian-evidence.v1",
        "source": "toe.bridge.TOEBridge",
        "result": result,
        "execution_evidence": execution,
    }


@lru_cache(maxsize=1)
def pythia_guardian_api() -> GuardianAPI:
    """Build the canonical guardian and require durable audit initialization.

    Privileged API traffic must never become less governed because durable
    audit cannot start. Platform, locking or configuration failures propagate
    to the caller and are surfaced as dependency-unavailable.
    """
    settings = ALHarasSettings.from_env(service="pythia")
    guardian = build_guardian(
        settings,
        allowed_operations=_PYTHIA_ALLOWED_OPERATIONS,
    )
    if guardian.audit.path is None:
        raise RuntimeError("PYTHIA AL HARAS durable audit is unavailable")
    return GuardianAPI(
        guardian,
        settings,
        evidence_provider=_toe_evidence,
    )

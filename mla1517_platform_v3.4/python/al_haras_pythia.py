"""PYTHIPhiMiner-local AL HARAS wiring to the canonical TOE bridge."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Mapping

from al_haras.runtime import GuardianAPI, build_guardian
from al_haras.settings import ALHarasSettings


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
        if not isinstance(result.get(name), Mapping)
        or not result[name].get("available", False)
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
    settings = ALHarasSettings.from_env(service="pythia")
    return GuardianAPI(
        build_guardian(settings),
        settings,
        evidence_provider=_toe_evidence,
    )

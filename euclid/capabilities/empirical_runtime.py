"""Explicit empirical operational-state binding at the canonical runtime boundary."""

from dataclasses import asdict
import re
import secrets

from .empirical_state_bridge import EmpiricalStateBridge, StateTransitionRequest


def bind_empirical_state(runtime, *, data_port, organ_id="empirical-state"):
    """Use the host's shared custody and AL HARAS + creator-rights dispatch.

    Binding grants no rights and installs no guardian. This is an operational
    state capability, not a parallel intelligence learner or identity root.
    """
    from al_haras import HashChainAudit
    from aethel.enterprise.entangled_custody import SystemDataPort
    from aethel.enterprise.persistent_entangled_custody import PersistentEntangledCustodyFabric
    from euclid.contracts import Authority
    from euclid.runtime import EuclidRuntime

    if not isinstance(runtime, EuclidRuntime) or runtime._closed:
        raise TypeError("open canonical EuclidRuntime required")
    if type(organ_id) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", organ_id) is None:
        raise ValueError("bounded path-free organ identifier required")
    if (
        not isinstance(data_port, SystemDataPort)
        or data_port.system != "euclid"
        or not isinstance(data_port.fabric, PersistentEntangledCustodyFabric)
    ):
        raise TypeError("shared persistent EUCLID data port required")
    secret = secrets.token_urlsafe(32)
    audit = HashChainAudit(runtime.state_dir / "empirical" / (organ_id + ".jsonl"))
    bridge = EmpiricalStateBridge(
        audit=audit,
        data_port=data_port,
        owner_id=runtime.creator_id,
        authorizer=lambda req: req.caller_id == runtime.creator_id
        and secrets.compare_digest(req.operator_token, secret),
    )

    class Specialist:
        def catalog(self):
            return [
                {
                    "capability_id": bridge.APPROVED_CAPABILITY_ID,
                    "operations": ["UPDATE_RELIABILITY"],
                    "budget_unit": "transition",
                    "cost": 1,
                    "authorization": "AL_HARAS_AND_CREATOR_RIGHTS",
                    "independently_qualified": False,
                }
            ]

        def handle(self, request):
            if (
                type(request) is not dict
                or set(request) != {"operation", "arguments"}
                or type(request["arguments"]) is not dict
                or set(request["arguments"]) != {"state_payload", "deadline_epoch", "max_budget"}
            ):
                raise ValueError("invalid empirical request fields")
            args = request["arguments"]
            req = StateTransitionRequest(
                bridge.APPROVED_CAPABILITY_ID,
                runtime.creator_id,
                request["operation"],
                args["state_payload"],
                args["deadline_epoch"],
                args["max_budget"],
                secret,
            )
            ok, receipt, reason = bridge.dispatch(req)
            return {
                "executed": ok,
                "status": reason,
                "receipt": asdict(receipt) if receipt else None,
            }

    specialist = Specialist()
    runtime.register_specialist(
        organ_id, specialist, operations=("UPDATE_RELIABILITY",), authority=Authority.PROPOSE
    )
    return specialist

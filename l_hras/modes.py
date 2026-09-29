"""The five modes — Part VII.

Multiply, Entangle, Swarm, Honey_Pot, Willow_Expose. Every mode is a
projection of the joint state and emits its own attestation; the verdict
conjoins all five.
"""

from __future__ import annotations

import itertools
from fractions import Fraction
from typing import Any, Optional, Sequence

from . import substrates
from .result import (
    CONSENSUS_FAILED,
    ENTANGLEMENT_BREAK,
    MULTIPLY_FAILED,
    SWARM_QUORUM_FAILED,
    WILLOW_FAILED,
    Ok,
    Result,
    error,
)
from .types import (
    AdversaryBelief,
    Attestation,
    CounterfactualPath,
    Decision,
    Decoy,
    Defense,
    EntangledIntelligence,
    Exposure,
    HoneyPot,
    InfoOp,
    Multiplication,
    Trap,
    WorkerResponse,
    digest_of,
)

_ids = itertools.count(1)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{next(_ids)}"


def _attest(attester: Any, event: str, payload: Any) -> Attestation:
    return attester.attest(event, payload)


# ---------------------------------------------------------------------------
# Mode 1 — Multiply (MULT1–3)
# ---------------------------------------------------------------------------


def _event_state_projection(event: Any, name: str, num_qubits: int) -> Any:
    """Project the event onto an intelligence's basis — deterministic:
    the event digest selects the basis index."""
    digest = digest_of({"intel": name, "event": event.canonical_payload()})
    index = int(digest[:8], 16) % (1 << num_qubits)
    return substrates.exact_basis(num_qubits, index)


def multiply(
    joint: Any, event: Any, digest: str, cfg: Any, attester: Any
) -> Result[Multiplication]:
    vectors = []
    for intel in joint.projection:
        joint_vec = joint.projection[intel]
        event_vec = _event_state_projection(event, intel, joint_vec.num_qubits)
        try:
            v = joint_vec.tensor(event_vec)
        except Exception as exc:
            return error(MULTIPLY_FAILED, intelligence=intel, reason=str(exc))
        if v is None:
            return error(MULTIPLY_FAILED, intelligence=intel)
        vectors.append(v)
    # combined = v_1 ⊗ ... ⊗ v_6 kept in factor form — the 2^36-dimensional
    # pure tensor is the tuple itself; materializing it is never required
    # (MULT1: cardinality = 2^len(vectors) counts mode combinations).
    combined = tuple(vectors)
    return Ok(
        Multiplication(
            vectors=vectors,
            combined=combined,
            cardinality=2 ** len(vectors),
            digest=digest,
            attestation=_attest(
                attester,
                "multiply",
                {"digest": digest, "vectors": len(vectors)},
            ),
            ok=True,
        )
    )


# ---------------------------------------------------------------------------
# Mode 2 — Entangle (ENT1–3)
# ---------------------------------------------------------------------------


def entangle(
    joint: Any, event: Any, attester: Any, cfg: Any = None
) -> Result[EntangledIntelligence]:
    if getattr(joint, "entangled_cache", None) is not None:
        return Ok(joint.entangled_cache)
    graph = joint.entanglement
    correlations = joint.correlations

    # Bell-state verification — the entanglement claim is exact (EI2–EI4).
    bell = substrates.bell_state()
    rank = substrates.schmidt_rank(bell)
    if rank != 2:
        return error(ENTANGLEMENT_BREAK, check="schmidt_rank", rank=rank)
    rho = substrates.partial_trace_bell(bell, 0)
    if not substrates.is_maximally_mixed(rho):
        return error(ENTANGLEMENT_BREAK, check="reduced_state")

    entangled = EntangledIntelligence(
        states=joint.projection,
        entanglement=graph,
        correlations=correlations,
        attestation=_attest(attester, "entangle", {"event": event.payload_digest()}),
        verified=True,
    )
    joint.entangled_cache = entangled
    return Ok(entangled)


# ---------------------------------------------------------------------------
# Mode 3 — Swarm (SW1–SW4)
# ---------------------------------------------------------------------------


class Guardian:
    """One swarm worker. Holds its own exact joint vector and votes on
    every event. ``compromised`` models a captured worker for quorum
    testing — a captured guardian always votes ``ignore``."""

    def __init__(self, idx: int, joint: Any, attestation: Attestation, aethel: Any):
        self.id = _new_id("guardian")
        self.idx = idx
        self.joint = joint
        self.attestation = attestation
        self.aethel = aethel
        self.compromised = False

    def respond(self, event: Any) -> WorkerResponse:
        if self.compromised:
            return WorkerResponse(guardian_id=self.id, ok=False, vote="ignore", digest="")
        vote = "block" if event.kind.value == "adversarial" else "monitor"
        return WorkerResponse(
            guardian_id=self.id,
            ok=True,
            vote=vote,
            digest=digest_of({"guardian": self.id, "event": event.payload_digest()}),
        )


class Swarm:
    def __init__(
        self, workers: list[Guardian], topology: dict, threshold: Fraction, attestation: Attestation
    ):
        self.id = _new_id("swarm")
        self.workers = workers
        self.topology = topology
        self.threshold = threshold
        self.attestation = attestation

    def subset(self, tenant_id: str) -> "Swarm":
        return Swarm(list(self.workers), dict(self.topology), self.threshold, self.attestation)


def spawn_guardian(cfg: Any, idx: int, aethel: Any, attester: Any) -> Result[Guardian]:
    joint = substrates.exact_zeros(cfg.state_dim)
    attestation = attester.self_attest({"event": "guardian_born", "idx": idx})
    return Ok(Guardian(idx=idx, joint=joint, attestation=attestation, aethel=aethel))


def build_swarm_topology(guardians: Sequence[Guardian]) -> dict[int, list[int]]:
    """Ring topology — each guardian observes its two neighbours."""
    n = len(guardians)
    return {i: sorted({(i - 1) % n, (i + 1) % n}) for i in range(n)}


def attest_swarm(guardians: Sequence[Guardian], attester: Any) -> Attestation:
    return attester.self_attest({"event": "swarm_born", "guardians": [g.id for g in guardians]})


def spawn_swarm(guardians: list[Guardian], threshold: Fraction, attester: Any) -> Result[Swarm]:
    topology = build_swarm_topology(guardians)
    return Ok(
        Swarm(
            workers=list(guardians),
            topology=topology,
            threshold=threshold,
            attestation=attest_swarm(guardians, attester),
        )
    )


def aggregate_votes(responses: Sequence[WorkerResponse]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for r in responses:
        counts[r.vote] = counts.get(r.vote, 0) + 1
    if not responses:
        return {"top_choice": None, "top_fraction": Fraction(0), "counts": counts}
    top_choice = max(counts, key=lambda c: counts[c])
    return {
        "top_choice": top_choice,
        "top_fraction": Fraction(counts[top_choice], len(responses)),
        "counts": counts,
    }


def consensus(
    swarm: Swarm, responses: Sequence[WorkerResponse], threshold: Fraction
) -> Result[Decision]:
    votes = aggregate_votes(responses)
    if votes["top_fraction"] < threshold:
        return error(CONSENSUS_FAILED, votes=str(votes["top_fraction"]))
    return Ok(Decision(choice=votes["top_choice"], votes=votes, threshold=threshold))


def swarm_defend(swarm: Swarm, event: Any, attester: Any) -> Result[Defense]:
    responses = [w.respond(event) for w in swarm.workers]
    ok_count = sum(1 for r in responses if r.ok)
    if Fraction(ok_count, len(responses)) < swarm.threshold:
        return error(SWARM_QUORUM_FAILED, ok_count=ok_count, total=len(responses))
    decision = consensus(swarm, responses, swarm.threshold)
    if decision.is_err:
        return decision
    return Ok(
        Defense(
            swarm=swarm,
            responses=responses,
            decision=decision.value,
            attestation=_attest(
                attester,
                "swarm_defend",
                {"votes": decision.value.votes["counts"]},
            ),
            ok=True,
        )
    )


# ---------------------------------------------------------------------------
# Mode 4 — Honey Pot (HP1–HP4)
# ---------------------------------------------------------------------------

_DECOY_TEMPLATES = {
    "credential": "vault_credential_{target}",
    "database": "reporting_db_{target}",
    "endpoint": "dmz_host_{target}",
    "generic": "asset_{target}",
}


def valuable_asset(target: str) -> str:
    return f"high_value_{target}"


def decoy_template_for(asset_class: str) -> str:
    return _DECOY_TEMPLATES.get(asset_class, _DECOY_TEMPLATES["generic"])


def fill_template(template: str, target: Any) -> Decoy:
    appearance = template.format(target=target)
    return Decoy(appearance=appearance, substance=Trap(trigger="", effect="capture"))


def derive_decoy(step: str, target: Any) -> Result[Decoy]:
    template = decoy_template_for(str(target))
    filled = fill_template(template, target)
    return Ok(
        Decoy(
            appearance=filled.appearance,
            substance=Trap(trigger=step, effect="capture"),
        )
    )


def place_honey_pots(
    joint: Any, paths: Sequence[CounterfactualPath], attester: Any
) -> Result[list[HoneyPot]]:
    if not paths:
        return Ok([])
    pots: list[HoneyPot] = []
    for path in paths:
        if not path.next_action_distribution:
            continue
        step = max(
            path.next_action_distribution,
            key=lambda a: path.next_action_distribution[a],
        )
        decoy = derive_decoy(step, path.expected_target)
        if decoy.is_err:
            return decoy
        trap = Trap(trigger=step, effect="capture_attacker_state")
        pots.append(
            HoneyPot(
                id=_new_id("pot"),
                decoy=decoy.value,
                path=path,
                trap=trap,
                appearance=valuable_asset(path.expected_target),
                substance=trap,
                attestation=_attest(
                    attester,
                    "honey_pot",
                    {"path": path.steps, "trap": trap.trigger},
                ),
            )
        )
    return Ok(pots)


# ---------------------------------------------------------------------------
# Mode 5 — Willow (WE1–WE6)
# ---------------------------------------------------------------------------


def choose_info_op(path: CounterfactualPath, decision: Decision) -> Result[InfoOp]:
    choice = decision.choice
    if choice == "block":
        return Ok(InfoOp(kind="confuse", target=path.adversary))
    if choice == "redirect":
        return Ok(InfoOp(kind="mislead", target=path.adversary))
    if choice == "entangle":
        return Ok(InfoOp(kind="delay", target=path.adversary))
    if choice == "monitor":
        return Ok(InfoOp(kind="expose", target=path.adversary))
    return error(WILLOW_FAILED, reason="ignore", choice=choice)


def _default_belief() -> AdversaryBelief:
    # |+><+| — a pure superposition so every info op moves the state:
    # dephase and depolarize lower its coherence, a rotation turns it.
    return AdversaryBelief(state=[[0.5, 0.5], [0.5, 0.5]], prior=None)


def apply_info_op(state: list[list[float]], op: InfoOp) -> Optional[list[list[float]]]:
    """Bend an adversary belief state (2x2 density matrix).

    confuse → depolarize toward I/2; mislead → basis-rotation (coherence
    shifts); delay → partial dephasing; expose → full dephasing.
    """
    if op.kind == "confuse":
        return substrates.mix_with_identity(state, 0.5)
    if op.kind == "mislead":
        return substrates.apply_unitary_to_density(state, substrates.rotation_unitary(0.7))
    if op.kind == "delay":
        return substrates.dephase(state, keep=0.5)
    if op.kind == "expose":
        return substrates.dephase(state, keep=0.0)
    return None


def willow(belief: AdversaryBelief, op: InfoOp) -> Result[AdversaryBelief]:
    bent = apply_info_op(belief.state, op)
    if bent is None:
        return error(WILLOW_FAILED, op=op.kind)
    return Ok(AdversaryBelief(state=bent, prior=belief.prior))


def willow_measure(before: AdversaryBelief, after: AdversaryBelief) -> float:
    """Measured belief divergence — Frobenius distance between the two
    density matrices (zero iff the states are identical)."""
    return substrates.state_distance(before.state, after.state)


def willow_expose(joint: Any, defense: Defense, attester: Any) -> Result[list[Exposure]]:
    if not defense.paths:
        return Ok([])
    exposures: list[Exposure] = []
    seen: set[str] = set()
    for path in defense.paths:
        key = path.adversary or "__unknown__"
        if key in seen:
            continue  # one bend per adversary per response — re-bending an
            # already-bent belief adds no measured information (WE5)
        seen.add(key)
        before = joint.adversary_beliefs.get(key, _default_belief())
        op = choose_info_op(path, defense.decision)
        if op.is_err:
            return op
        after = willow(before, op.value)
        if after.is_err:
            return after
        kld = willow_measure(before, after.value)
        if kld <= 0:
            # Belief saturated at its fixed point — re-ground from a
            # fresh prior so the measurement is meaningful (WE5).
            before = _default_belief()
            after = willow(before, op.value)
            if after.is_err:
                return after
            kld = willow_measure(before, after.value)
            if kld <= 0:
                return error(WILLOW_FAILED, kld=kld)
        joint.adversary_beliefs[key] = after.value
        exposures.append(
            Exposure(
                adversary=path.adversary,
                before=before,
                after=after.value,
                kl=kld,
                attestation=_attest(attester, "willow", {"path": path.steps, "kl": kld}),
            )
        )
    return Ok(exposures)

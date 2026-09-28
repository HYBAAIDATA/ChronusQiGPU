"""Federation and tenant isolation — Part XII (FED1–FED4)."""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any


@dataclass
class Peer:
    """A federated Guardian endpoint — ``ingest_threat`` is the only
    direction threat data moves."""

    id: str
    authenticated: bool = True
    inbox: list[Any] = field(default_factory=list)

    def ingest_threat(self, threat: Any) -> None:
        self.inbox.append(threat)


@dataclass
class Federation:
    peers: list[Peer]
    topology: dict[str, list[str]]
    threshold: Fraction = Fraction(2, 3)


def build_federation_topology(peers: list[Peer]) -> dict[str, list[str]]:
    ids = [p.id for p in peers]
    return {pid: [q for q in ids if q != pid] for pid in ids}


def federate(peers: list[Peer]) -> Federation:
    return Federation(
        peers=list(peers),
        topology=build_federation_topology(peers),
        threshold=Fraction(2, 3),
    )


def share_threat(federation: Federation, threat: Any) -> int:
    delivered = 0
    for peer in federation.peers:
        if peer.authenticated:
            peer.ingest_threat(threat)
            delivered += 1
    return delivered


@dataclass
class TenantNamespace:
    tenant_id: str
    aethel: Any
    policy: Any
    swarm: Any


def tenant_isolate(lhras: Any, tenant_id: str) -> TenantNamespace:
    return TenantNamespace(
        tenant_id=tenant_id,
        aethel=lhras.aethel.subspace(tenant_id),
        policy=lhras.policy.subset(tenant_id),
        swarm=lhras.swarm.subset(tenant_id),
    )

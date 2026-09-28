"""Attestation — Part XI.

Every operator emits :class:`Attestation` records signed by the trust
root. Compositions form a Merkle chain whose root is itself attested —
``attest_verify`` re-derives both the chain and the threshold policy.
The substrate layer (``kellogg.attest``) binds each payload's canonical
digest and Zeckendorf/Cassini slice into ``substrate``.
"""

from __future__ import annotations

import hashlib
import itertools
from typing import Any, Optional, Sequence

from .result import ATTESTATION_FAILURE, Ok, Result, error
from .types import Attestation, CompositeAttestation, TrustRoot, digest_of

_ids = itertools.count(1)


def _new_id(prefix: str = "att") -> str:
    return f"{prefix}-{next(_ids)}"


class Attester:
    """Issues attestations rooted in the trust root (CONSUME:toe.unified
    .attestation.Attester — implemented here against the declared seam)."""

    def __init__(self, root: TrustRoot, aethel: Any = None, lifecycle: Optional[dict] = None):
        self.root = root
        self.aethel = aethel
        self.lifecycle = dict(lifecycle or {})
        self.issued: list[Attestation] = []

    def _bind(self, event: str, payload: Any) -> Attestation:
        digest = digest_of({"event": event, "payload": payload})
        try:
            substrate = self._substrate_binding(payload)
        except Exception:
            substrate = {}
        att = Attestation(
            id=_new_id(),
            event=event,
            payload=payload,
            digest=digest,
            signature=self.root.sign({"attestation": digest}),
            substrate=substrate,
        )
        self.issued.append(att)
        return att

    def _substrate_binding(self, payload: Any) -> dict[str, Any]:
        from kellogg.attest import attest as kellogg_attest

        bound = kellogg_attest(payload if isinstance(payload, dict) else {"value": str(payload)})
        return {
            "schema": bound.get("schema"),
            "digest": bound.get("digest"),
            "zeckendorf": bound.get("zeckendorf"),
            "cassini": bound.get("cassini"),
        }

    def self_attest(self, event: Any) -> Attestation:
        """Attest an internal state transition (standing, throttle, break
        glass, self-state)."""
        return self._bind(
            event.get("event", "self") if isinstance(event, dict) else str(event),
            event if isinstance(event, dict) else {"value": event},
        )

    def attest(self, event: str, payload: Any) -> Attestation:
        return self._bind(event, payload)

    def verify(self, attestation: Attestation) -> bool:
        expected = digest_of({"event": attestation.event, "payload": attestation.payload})
        if expected != attestation.digest:
            return False
        return self.root.verify(attestation.signature, {"attestation": attestation.digest})


def merkle_chain(links: Sequence[Attestation]) -> list[str]:
    """Pairwise SHA-256 chain over link digests. Returns the leaf→root
    level digests; the final element is the chain root."""
    level = [a.digest for a in links]
    if not level:
        return []
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [
            hashlib.sha256((level[i] + level[i + 1]).encode("utf-8")).hexdigest()
            for i in range(0, len(level), 2)
        ]
    return level


def merkle_root_digest(links: Sequence[Attestation]) -> str:
    chain = merkle_chain(links)
    return chain[-1] if chain else ""


def attest_compose(
    links: Sequence[Optional[Attestation]],
    attester: Attester,
    policy: str = "unanimous",
    k: int = 4,
) -> Result[CompositeAttestation]:
    """Compose link attestations into a Merkle-anchored composite (AC1–AC3)."""
    present = [a for a in links if a is not None]
    if not present:
        return error(ATTESTATION_FAILURE, reason="no links")
    if k > len(links):
        return error(ATTESTATION_FAILURE, reason=f"k={k} exceeds links={len(links)}")
    if policy == "unanimous" and len(present) < len(links):
        return error(
            ATTESTATION_FAILURE,
            reason="unanimous policy requires every link",
            present=len(present),
            required=len(links),
        )
    if len(present) < k:
        return error(
            ATTESTATION_FAILURE,
            reason="threshold unmet",
            present=len(present),
            k=k,
        )
    for link in present:
        if not attester.verify(link):
            return error(ATTESTATION_FAILURE, reason="link signature invalid", link=link.id)

    chain_digest = merkle_root_digest(list(links)) if all(links) else merkle_root_digest(present)
    root = attester.self_attest(
        {"event": "composite_root", "chain": chain_digest, "policy": policy, "k": k}
    )
    return Ok(
        CompositeAttestation(
            chain=[a if a is not None else _null_link() for a in links],
            root=root,
            policy=policy,
            k=k,
        )
    )


def _null_link() -> Attestation:
    return Attestation(id="null", event="absent", payload=None, digest="0" * 64, signature="")


def merkle_verify(chain: Sequence[Attestation], root: Attestation, attester: Attester) -> bool:
    real = [a for a in chain if a.id != "null"]
    if root.payload.get("chain") != merkle_root_digest(real):
        return False
    return attester.verify(root)


def threshold_satisfied(policy: str, k: int, chain: Sequence[Attestation]) -> bool:
    present = sum(1 for a in chain if a.id != "null")
    if policy == "unanimous":
        return present == len(chain)
    return present >= k


def attest_verify(composite: CompositeAttestation, attester: Attester) -> bool:
    return merkle_verify(composite.chain, composite.root, attester) and threshold_satisfied(
        composite.policy, composite.k, composite.chain
    )

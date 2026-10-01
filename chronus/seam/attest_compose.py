"""Attestation composition. Prerequisite for F4.

A composite is valid only if every constituent link verifies and the
Merkle root of the subjects matches. Threshold policy is declared.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Set

from .types import (
    AttestationLink,
    Err,
    Ok,
    Result,
    SeamError,
    ThresholdPolicy,
    digest_of,
    sign_digest,
    verify_link,
)


def merkle_root(subjects: Sequence[str]) -> str:
    """Order-independent Merkle root of constituent subjects."""
    leaves = sorted(digest_of(subject.encode("utf-8")) for subject in subjects)
    if not leaves:
        return digest_of(b"empty")
    layer = leaves
    while len(layer) > 1:
        next_layer: List[str] = []
        for index in range(0, len(layer), 2):
            left = layer[index]
            right = layer[index + 1] if index + 1 < len(layer) else left
            next_layer.append(digest_of(f"{left}|{right}".encode("utf-8")))
        layer = next_layer
    return layer[0]


def threshold_for(
    policy: ThresholdPolicy,
    n: int,
    k: Optional[int] = None,
) -> int:
    if policy is ThresholdPolicy.unanimous:
        return n
    if policy is ThresholdPolicy.majority:
        return (n // 2) + 1
    if policy is ThresholdPolicy.at_least_k:
        return int(k or n)
    if policy is ThresholdPolicy.weighted:
        return int(k or ((n // 2) + 1))
    return n


@dataclass
class CompositeAttestation:
    links: List[AttestationLink]
    root: str
    threshold: int
    policy: ThresholdPolicy

    def as_dict(self) -> dict:
        return {
            "links": [link.as_dict() for link in self.links],
            "root": self.root,
            "threshold": self.threshold,
            "policy": self.policy.value,
        }


def attest_compose(
    links: Sequence[AttestationLink],
    policy: ThresholdPolicy = ThresholdPolicy.majority,
    k: Optional[int] = None,
    issuers: Optional[Set[str]] = None,
) -> Result[CompositeAttestation]:
    """Compose verified links, optionally constraining legitimate issuers."""
    if not links:
        return Err(SeamError.attestation_failure, "empty attestation set")
    for link in links:
        if not verify_link(link):
            return Err(SeamError.attestation_failure, f"link {link.subject}")
        if issuers is not None and link.issuer not in issuers:
            return Err(
                SeamError.attestation_failure,
                f"issuer not allowed: {link.issuer}",
            )
    root = merkle_root([link.subject for link in links])
    return Ok(
        CompositeAttestation(
            links=list(links),
            root=root,
            threshold=threshold_for(policy, len(links), k),
            policy=policy,
        )
    )


def weighted_sum(
    links: Sequence[AttestationLink],
    weights: Optional[Sequence[float]] = None,
) -> float:
    if not links:
        return 0.0
    if weights is None:
        return float(len(links))
    return float(sum(weights[: len(links)]))


def attest_verify(
    composite: CompositeAttestation,
    weights: Optional[Sequence[float]] = None,
    issuers: Optional[Set[str]] = None,
) -> bool:
    if not all(verify_link(link) for link in composite.links):
        return False
    if issuers is not None and not all(
        link.issuer in issuers for link in composite.links
    ):
        return False
    if merkle_root([link.subject for link in composite.links]) != composite.root:
        return False
    n = len(composite.links)
    if composite.policy is ThresholdPolicy.majority:
        return n >= composite.threshold
    if composite.policy is ThresholdPolicy.unanimous:
        return n == composite.threshold and n > 0
    if composite.policy is ThresholdPolicy.at_least_k:
        return n >= composite.threshold
    if composite.policy is ThresholdPolicy.weighted:
        return weighted_sum(composite.links, weights) >= composite.threshold
    return False


def sign_link(subject: str, issuer: str) -> str:
    return sign_digest(subject, issuer)

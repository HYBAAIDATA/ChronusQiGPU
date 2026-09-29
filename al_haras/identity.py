"""Authenticated-principal derivation; request actor headers are never proof."""

from dataclasses import dataclass
from typing import Mapping


class UnauthenticatedPrincipal(PermissionError):
    pass


@dataclass(frozen=True)
class VerifiedIdentity:
    method: str
    subject: str
    verified: bool
    audience: str | None = None


def derive_authenticated_actor(
    identities: Mapping[str, VerifiedIdentity], *, service_audience: str
) -> str:
    for method in ("mtls", "oidc", "spiffe"):
        identity = identities.get(method)
        if (
            not identity
            or not identity.verified
            or identity.method != method
            or not identity.subject
        ):
            continue
        if identity.audience not in (None, service_audience):
            continue
        return identity.subject
    raise UnauthenticatedPrincipal("no verified mTLS, OIDC, or SPIFFE principal")

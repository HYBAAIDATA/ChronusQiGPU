from typing import Literal

from fastapi import APIRouter, Depends, Query

from chronus.service.api import claims
from chronus.service.api.errors import ApiError
from chronus.service.api.schemas import Capability, Blocker, Qualification
from chronus.service.api.security import Principal, require

router = APIRouter()


@router.get("", response_model=list[Capability], summary="Capability claims")
async def list_claims(
    disposition: Literal["supported", "unverified", "withdrawn"] | None = Query(default=None),
    _: Principal = Depends(require("evidence:read")),
):
    items = claims.load_audit().claims
    if disposition:
        items = tuple(c for c in items if c.disposition == disposition)
    return [Capability(**vars(c)) for c in items]


@router.get("/{claim_id}", response_model=Capability, summary="One claim")
async def get_claim(claim_id: str, _: Principal = Depends(require("evidence:read"))):
    for claim in claims.load_audit().claims:
        if claim.id == claim_id:
            return Capability(**vars(claim))
    raise ApiError(404, "claim_not_found", "Claim not found", f"No claim {claim_id!r}.")


qualification_router = APIRouter()


@qualification_router.get("", response_model=Qualification,
                          summary="Release posture and open blockers")
async def qualification(_: Principal = Depends(require("evidence:read"))):
    audit = claims.load_audit()
    counts = {"supported": 0, "unverified": 0, "withdrawn": 0}
    for claim in audit.claims:
        counts[claim.disposition] += 1
    return Qualification(
        posture=audit.posture, reviewed_at=audit.reviewed_at, commit=audit.commit,
        counts=counts, blockers=[Blocker(**vars(b)) for b in audit.blockers],
    )

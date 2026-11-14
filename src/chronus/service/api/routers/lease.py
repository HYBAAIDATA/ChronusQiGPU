from fastapi import APIRouter, Depends

from chronus.service.api.lease import current_lease
from chronus.service.api.schemas import Lease

router = APIRouter()


@router.get("", response_model=Lease, summary="Your lease")
async def get_lease(lease: Lease = Depends(current_lease)):
    return lease

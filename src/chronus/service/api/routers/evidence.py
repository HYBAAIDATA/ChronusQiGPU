from fastapi import APIRouter, Depends

from chronus.service.api import store
from chronus.service.api.schemas import Receipt
from chronus.service.api.security import Principal, require

router = APIRouter()


@router.get("/{receipt_id}", response_model=Receipt, summary="Receipt by id")
async def receipt(receipt_id: str, principal: Principal = Depends(require("evidence:read"))):
    return store.get_receipt(principal.tenant_id, receipt_id)

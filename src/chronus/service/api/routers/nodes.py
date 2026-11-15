from fastapi import APIRouter, Depends, Query

from chronus.service.api import store
from chronus.service.api.pagination import clamp_limit, decode_cursor, encode_cursor
from chronus.service.api.schemas import CapacitySlot, Node, NodePage
from chronus.service.api.security import Principal, require

router = APIRouter()


@router.get("", response_model=NodePage, summary="List fleet nodes")
async def list_nodes(
    limit: int | None = Query(default=None, ge=1, le=100),
    cursor: str | None = Query(default=None),
    region: str | None = Query(default=None, max_length=32),
    _: Principal = Depends(require("fleet:read")),
):
    items, next_cursor = store.list_nodes(clamp_limit(limit), decode_cursor(cursor), region)
    return NodePage(items=items,
                    next_cursor=encode_cursor(next_cursor) if next_cursor else None)


@router.get("/{node_id}", response_model=Node, summary="Get one node")
async def get_node(node_id: str, _: Principal = Depends(require("fleet:read"))):
    return store.get_node(node_id)


capacity_router = APIRouter()


@capacity_router.get("", response_model=list[CapacitySlot], summary="Free slots by region")
async def capacity(_: Principal = Depends(require("workloads:read"))):
    return store.capacity()

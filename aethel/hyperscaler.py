"""Hyperscaler GPU fork: folded Zeckendorf is the working form.

H1 put stores a ZeckendorfVector.
H2 working returns the vector.
H3 every mask is non-adjacent.
H4 unit count snaps on the Lucas/Pisot ladder.
H5 egress unfolds byte-identically.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from aethel.encoding import ZeckendorfVector, fold, unfold
from aethel.storage import AddressSpace, FibonacciAddress

INVARIANTS = ("H1", "H2", "H3", "H4", "H5")


def vector_to_bytes(vector: ZeckendorfVector) -> bytes:
    return json.dumps(
        {"blocks": [list(p) for p in vector.blocks], "total_bytes": vector.total_bytes}
    ).encode("utf-8")


def vector_from_bytes(raw: bytes) -> ZeckendorfVector:
    obj = json.loads(raw.decode("utf-8"))
    blocks = tuple((int(a), int(b)) for a, b in obj["blocks"])
    return ZeckendorfVector(blocks=blocks, total_bytes=int(obj["total_bytes"]))


def mask_merkle(masks: Tuple[int, ...]) -> str:
    node = b""
    for mask in masks:
        leaf = hashlib.sha256(str(mask).encode("ascii")).digest()
        node = hashlib.sha256(node + leaf).digest()
    return node.hex() if node else hashlib.sha256(b"").hexdigest()


@dataclass(frozen=True)
class FoldedRecord:
    address: FibonacciAddress
    units: int
    total_bytes: int
    work_items: int
    merkle: str

    def as_dict(self) -> Dict[str, Any]:
        return {
            "index": self.address.index,
            "fibonacci": self.address.value,
            "folded_units": self.units,
            "source_bytes": self.total_bytes,
            "work_items": self.work_items,
            "merkle": self.merkle,
            "working_form": "zeckendorf",
        }


class HyperscalerSku:
    def __init__(self) -> None:
        self.space = AddressSpace()
        self._index: List[FibonacciAddress] = []
        self._chain: List[str] = []

    def put(self, payload: bytes, job_id: str = "hs") -> FoldedRecord:
        vector = fold(payload)
        if not vector.verify():
            raise ValueError("H3")
        masks = tuple(mask for _o, mask in vector.blocks)
        merkle = mask_merkle(masks)
        prev = self._chain[-1] if self._chain else ""
        chained = hashlib.sha256((prev + merkle).encode("ascii")).hexdigest()
        self._chain.append(chained)
        from chronus.seam.scale import scale_job

        scale = scale_job(job_id, max(vector.folded_units, 1))
        addr = self.space.write(vector_to_bytes(vector))
        self._index.append(addr)
        return FoldedRecord(
            addr, vector.folded_units, vector.total_bytes, scale.work_items, chained
        )

    def working(self, address: FibonacciAddress) -> ZeckendorfVector:
        vec = vector_from_bytes(self.space.read(address))
        if not vec.verify():
            raise ValueError("H3")
        return vec

    def masks(self, address: FibonacciAddress) -> Tuple[int, ...]:
        return tuple(mask for _off, mask in self.working(address).blocks)

    def egress(self, address: FibonacciAddress) -> bytes:
        return unfold(self.working(address))

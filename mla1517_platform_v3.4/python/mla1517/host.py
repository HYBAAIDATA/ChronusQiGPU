from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Tile:
    tile_id: int
    start: int
    end: int


@dataclass(frozen=True)
class HostGPUPlan:
    total_items: int
    lanes: int
    mode: str = "host_gpu_overlay"
    backend: str = "cpu_reference"

    def __post_init__(self):
        if self.total_items < 0 or self.lanes < 1:
            raise ValueError("total_items >= 0 and lanes >= 1 are required")
        if self.mode not in {"mla1517_gpu", "integrated_iGPU", "host_gpu_overlay", "cpu_reference"}:
            raise ValueError("unsupported mode")

    def tiles(self) -> tuple[Tile, ...]:
        if self.total_items == 0:
            return ()
        count = min(self.lanes, self.total_items)
        base, extra = divmod(self.total_items, count)
        out, start = [], 0
        for tile_id in range(count):
            width = base + (1 if tile_id < extra else 0)
            out.append(Tile(tile_id, start, start + width))
            start += width
        return tuple(out)

    def validate(self) -> None:
        tiles = self.tiles()
        if not tiles:
            if self.total_items != 0:
                raise ValueError("empty plan for non-empty workload")
            return
        if tiles[0].start != 0 or tiles[-1].end != self.total_items:
            raise ValueError("plan does not cover workload")
        for left, right in zip(tiles, tiles[1:]):
            if left.end != right.start:
                raise ValueError("plan has a gap or overlap")
        if any(t.end <= t.start for t in tiles):
            raise ValueError("empty tile")

    def manifest(self) -> dict[str, object]:
        self.validate()
        return {
            **asdict(self),
            "tiles": [asdict(t) for t in self.tiles()],
            "coverage": self.total_items,
        }


def execute_reference(values: Iterable[T], plan: HostGPUPlan, kernel: Callable[[T], T]) -> list[T]:
    """Deterministic CPU fallback for the host-GPU overlay contract."""
    items = list(values)
    if len(items) != plan.total_items:
        raise ValueError("value count does not match plan")
    plan.validate()
    out = [None] * len(items)
    for tile in plan.tiles():
        for i in range(tile.start, tile.end):
            out[i] = kernel(items[i])
    return out

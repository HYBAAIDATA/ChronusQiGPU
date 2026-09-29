"""Cross-backend exact conformance vector runner."""

from dataclasses import dataclass
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class Backend:
    name: str
    execute: Callable[[str, Any], Any]
    available: bool = True


VECTORS = (
    *(("fibonacci", n) for n in (15, 31, 50, 76)),
    *(("lucas", n) for n in (15, 31, 50, 76)),
    *(("zeckendorf", n) for n in range(10000)),
    *(("cassini", n) for n in range(1, 10001)),
    *((family, n) for family in ("padovan", "narayana", "tribonacci") for n in range(31)),
    ("m32_laplacian_gap", None),
    ("m32_hermitian_gap", None),
    ("quantum_hadamard_2q", None),
    ("quantum_cnot_2q", None),
    ("exact_tensor_round_trip", None),
)


class BackendDivergence(AssertionError):
    pass


def run_all_backends(backends: Iterable[Backend], vectors=VECTORS) -> int:
    active = tuple(b for b in backends if b.available)
    if len(active) < 2:
        raise ValueError("conformance requires at least two available backends")
    count = 0
    for kind, value in vectors:
        results = [b.execute(kind, value) for b in active]
        if any(result != results[0] for result in results[1:]):
            raise BackendDivergence(f"{kind}({value})")
        count += 1
    return count

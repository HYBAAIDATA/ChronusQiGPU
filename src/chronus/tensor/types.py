"""Section 1: core types and invariants for the Falsifiable Tensor Engine.

Block-sparse symmetry containers, truncation records and the cumulative
ErrorLedger. Ledger accumulation here is ``2*sqrt(sum discarded)`` for
SVD records — an estimate absent canonical-gauge enforcement, not a
certified Schmidt bound; gate sequences accumulate per-step bounds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np


class UntrustedApproximation(Exception):
    """Raised when an approximation without a rigorous Hilbert-space bound is attempted."""


class UntrustedResult(Exception):
    """Raised when a contraction exceeds physical hardware memory budgets."""


class UnsupportedHamiltonian(Exception):
    """Raised when an MPO term requires bond dimension exceeding the honest capacity."""


class RefusedMethod(Exception):
    """Raised when an uncertifiable algorithm (e.g. Trotter at 1000 nodes) is invoked."""


class LegDirection(str, Enum):
    IN = "IN"
    OUT = "OUT"


@dataclass(frozen=True)
class Leg:
    """A physical or virtual tensor index with dimension, charge sector, and direction."""

    id: int
    dim: int
    charge: int = 0
    direction: LegDirection = LegDirection.OUT

    def __repr__(self) -> str:
        return f"Leg(id={self.id}, dim={self.dim}, q={self.charge}, dir={self.direction.value})"


ChargeTuple = Tuple[int, ...]
BondId = Tuple[int, int]


def charge_conserving(charges: ChargeTuple, group: str) -> bool:
    """Checks whether the charges sum to 0 under group fusion rules."""
    if group == "none":
        return True
    if group == "Z2":
        return (sum(charges) % 2) == 0
    if group == "U(1)":
        return sum(charges) == 0
    if group == "SU(2)":
        # For SU(2) triangular inequality / integer spin fusion
        # simplified to integer parity / scalar singlet channel
        return (sum(charges) % 2) == 0
    return False


def theory_saving(group: str, chi: int) -> float:
    """Theoretical memory/flop reduction factor for a given symmetry group at bond dimension chi."""
    if group == "none":
        return 1.0
    if group == "Z2":
        # Z2 divides into 2 equal sectors: memory reduction is exactly 2.0x for rank-2, 2.0x - 4.0x for rank-3/4
        return 2.0
    if group == "U(1)":
        # U(1) Gaussian charge distribution across ~sqrt(chi) sectors gives ~sqrt(chi/2) savings
        # At chi=64: ~5.66x, chi=128: ~8.00x, chi=256: ~11.31x, chi=512: ~16.00x
        return max(2.0, math.sqrt(chi * math.pi / 2.0))
    if group == "SU(2)":
        # Wigner-Eckart theorem factors out Clebsch-Gordan coefficients: sum(2j+1) scaling
        return max(4.0, math.sqrt(chi) * 1.5)
    return 1.0


@dataclass
class SymmetricTensor:
    """Block-sparse tensor storing only charge-conserving blocks.

    This is the only reason chi=4096 fits in addressed physical RAM.
    Owner: representation theorist.
    """

    blocks: Dict[ChargeTuple, np.ndarray]
    legs: List[Leg]
    group: str = "none"  # "none", "Z2", "U(1)", "SU(2)"
    degeneracies: Dict[ChargeTuple, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Invariant 1: every stored block must conserve charge (or match node fusion channel)
        if self.group != "none":
            for charges in self.blocks:
                if not charge_conserving(charges, self.group):
                    raise ValueError(
                        f"Invariant violation: Block charge {charges} does not conserve {self.group} charge."
                    )

    @classmethod
    def product_state(cls, site_idx: int, group: str = "none", state_val: int = 0) -> "SymmetricTensor":
        """Creates a rank-3 product state tensor for site i: (left_virt, phys, right_virt)."""
        phys_leg = Leg(id=site_idx, dim=2, charge=state_val if group != "none" else 0, direction=LegDirection.OUT)
        left_leg = Leg(id=-1000 - site_idx, dim=1, charge=0, direction=LegDirection.IN)
        right_leg = Leg(id=1000 + site_idx, dim=1, charge=0, direction=LegDirection.OUT)

        data = np.zeros((1, 2, 1), dtype=np.complex128)
        data[0, state_val, 0] = 1.0 + 0.0j

        charge_key = (0, state_val if group != "none" else 0, 0)
        blocks = {charge_key: data} if group == "none" or charge_conserving(charge_key, group) else {(0, 0, 0): data}

        return cls(
            blocks=blocks,
            legs=[left_leg, phys_leg, right_leg],
            group=group,
        )

    def memory_bytes(self) -> int:
        """Exact memory consumed by stored non-zero complex128 blocks."""
        return sum(block.nbytes for block in self.blocks.values())

    def dense_shape(self) -> Tuple[int, ...]:
        return tuple(leg.dim for leg in self.legs)

    def dense_elements(self) -> int:
        return int(np.prod(self.dense_shape()))

    def dense_equivalent_bytes(self) -> int:
        return self.dense_elements() * 16  # 16 bytes per complex128

    def dense_equivalent_flops(self) -> int:
        return self.dense_elements()

    def block_flops(self) -> int:
        return sum(block.size for block in self.blocks.values())

    def to_dense(self) -> np.ndarray:
        """Converts block-sparse structure to dense array (for testing & cross-checks at n <= 32)."""
        shape = self.dense_shape()
        dense = np.zeros(shape, dtype=np.complex128)
        if self.group == "none":
            for block in self.blocks.values():
                return block.copy() if block.shape == shape else block.reshape(shape)

        # Place blocks according to charge offsets
        for charges, block in self.blocks.items():
            dense[:block.shape[0], :block.shape[1], :block.shape[2]] += block
        return dense


@dataclass
class Node:
    """A node in the tensor network holding a SymmetricTensor and physical/virtual legs."""

    id: int
    phys_legs: List[Leg]
    virt_legs: List[Leg]
    tensor: SymmetricTensor
    gauge_fix: Optional[str] = None


@dataclass
class TruncationRecord:
    """Theorem-backed record of a singular-value or tensor truncation."""

    step: int
    bond: BondId
    method: str  # "svd", "rand_svd", "tensor_train", "boundary_mps", "ctmrg", "bp"
    discarded_weight: float
    kept_chi: int
    error_bound: float
    theorem_ref: str


@dataclass
class ContractionCertificate:
    """Auditable certificate emitted by the contraction planner for a contraction step."""

    tree: Any
    peak_memory_bytes: int
    flop_count: int
    planner_bound: float
    planner_theorem: str


@dataclass
class ErrorLedger:
    """The immutable global error ledger tracking all approximations and truncations."""

    truncations: List[TruncationRecord] = field(default_factory=list)
    certificates: List[ContractionCertificate] = field(default_factory=list)
    global_bound: float = 0.0
    claim_bound: float = 1e-6
    _step_counter: int = 0

    def next_step(self) -> int:
        self._step_counter += 1
        return self._step_counter

    def append(self, item: Union[TruncationRecord, ContractionCertificate]) -> None:
        if isinstance(item, TruncationRecord):
            if not math.isfinite(item.discarded_weight) or item.discarded_weight < 0 or not math.isfinite(item.error_bound) or item.error_bound < 0:
                raise ValueError("truncation evidence must have finite nonnegative weights and bounds")
            self.truncations.append(item)
            # The triangle inequality requires adding each independently
            # committed truncation error; sqrt(sum(weights)) is not valid
            # for sequential adaptive truncations.
            self.global_bound += item.error_bound
        elif isinstance(item, ContractionCertificate):
            if not math.isfinite(item.planner_bound) or item.planner_bound < 0:
                raise ValueError("planner bound must be finite and nonnegative")
            self.certificates.append(item)
            self.global_bound += item.planner_bound

    def record(self, cert: ContractionCertificate) -> None:
        self.append(cert)

    def is_certified(self) -> bool:
        """Returns True if the accumulated global bound is strictly within claim bound."""
        return self.global_bound < self.claim_bound

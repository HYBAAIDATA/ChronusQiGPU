"""Kernel signatures — K6, K7, K8. Every named kernel declares its physics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from igpu.seam.types import KERNEL_CLASS, KernelClass, KernelName


@dataclass(frozen=True)
class CheckpointStrategy:
    interval: int
    max_in_flight: int
    epsilon: float

    def pebbles(self, n_steps: int, levels: int) -> int:
        n = max(1, n_steps // max(1, self.interval))
        k = max(1, levels)
        return k * (n - 1) + 1

    def time_factor(self, n_steps: int, levels: int) -> int:
        n = max(1, n_steps // max(1, self.interval))
        k = max(1, levels)
        return (2 * n - 1) ** k

    def as_dict(self) -> dict:
        return {"interval": self.interval, "max_in_flight": self.max_in_flight, "epsilon": self.epsilon}


DEFAULT_CHECKPOINT = CheckpointStrategy(interval=8, max_in_flight=4, epsilon=0.5)


@dataclass(frozen=True)
class KernelSignature:
    name: KernelName
    klass: KernelClass
    reversible: bool
    inverse: Optional[KernelName]
    uncomputable: bool
    checkpointable: bool
    checkpoint_strategy: Optional[CheckpointStrategy]
    landauer_bits: int
    fault_tolerant: bool = False

    def as_dict(self) -> dict:
        return {
            "name": self.name.value,
            "klass": self.klass.value,
            "reversible": self.reversible,
            "inverse": None if self.inverse is None else self.inverse.value,
            "uncomputable": self.uncomputable,
            "checkpointable": self.checkpointable,
            "checkpoint_strategy": None if self.checkpoint_strategy is None else self.checkpoint_strategy.as_dict(),
            "landauer_bits": self.landauer_bits,
            "fault_tolerant": self.fault_tolerant,
        }


def _irreversible(name: KernelName, bits: int = 1) -> KernelSignature:
    return KernelSignature(name, KERNEL_CLASS.get(name, KernelClass.coordination), False, None, False, False, None, bits)


def _reversible(name: KernelName, inverse: KernelName) -> KernelSignature:
    klass = KERNEL_CLASS.get(name, KernelClass.compute_heavy)
    return KernelSignature(name, klass, True, inverse, True, True, DEFAULT_CHECKPOINT, 0)


SIGNATURES: Dict[KernelName, KernelSignature] = {}
for _name in KernelName:
    SIGNATURES[_name] = _irreversible(_name)

for _rev in (KernelName.reversible_matmul_f4, KernelName.reversible_qfi_pure):
    SIGNATURES[_rev] = _reversible(_rev, _rev)


def signature_of(kernel: KernelName) -> KernelSignature:
    return SIGNATURES[kernel]


def inverse_of(kernel: KernelName) -> Optional[KernelName]:
    return signature_of(kernel).inverse

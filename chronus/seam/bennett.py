"""Bennett pebble / checkpoint uncomputation (A4, K6–K8).

dispatch_reversible runs a reversible step chain:
  forward with snapshots, copy the live result (Landauer paid here),
  invert back through checkpoints so garbage is wiped.

This is the host schedule. It does not recover CV^2 on CMOS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

from igpu.seam.signatures import CheckpointStrategy, DEFAULT_CHECKPOINT
from igpu.seam.thermodynamics import Technology, ThermodynamicMeasurement, measure_thermodynamic
from igpu.seam.types import Err, KernelName, Ok, Result, SeamError


@dataclass
class Checkpoint:
    step: int
    state: bytes


@dataclass
class BennettRun:
    steps: int
    checkpoints: List[Checkpoint] = field(default_factory=list)
    live: bytes = b""
    restored: bytes = b""
    garbage_uncomputed: bool = False
    landauer_bits: int = 0
    measurement: Optional[ThermodynamicMeasurement] = None


def _xor_step(state: bytes, step: int) -> bytes:
    if not state:
        state = b"\x00"
    delta = (step * 17 + 3) & 0xFF
    return bytes(b ^ delta for b in state)


def dispatch_reversible(
    kernel: KernelName,
    inputs: Sequence[bytes],
    total_steps: int = 16,
    strategy: Optional[CheckpointStrategy] = None,
    technology: Technology = Technology.cpu_reference,
    forward: Optional[Callable[[bytes, int], bytes]] = None,
    inverse: Optional[Callable[[bytes, int], bytes]] = None,
) -> Result[BennettRun]:
    if total_steps <= 0:
        return Err(SeamError.unknown, "total_steps")
    strat = strategy or DEFAULT_CHECKPOINT
    if strat.interval <= 0 or strat.max_in_flight <= 0:
        return Err(SeamError.unknown, "checkpoint_strategy")
    fwd = forward or _xor_step
    inv = inverse or _xor_step
    current = bytes(inputs[0]) if inputs else b"\x00"
    initial = current
    run = BennettRun(steps=total_steps)

    for step in range(total_steps):
        if step % strat.interval == 0:
            if len(run.checkpoints) >= strat.max_in_flight:
                run.checkpoints.pop(0)
            run.checkpoints.append(Checkpoint(step, current))
        current = fwd(current, step)

    run.live = bytes(current)
    run.landauer_bits = max(1, len(run.live) * 8)

    cursor = current
    for step in range(total_steps - 1, -1, -1):
        cursor = inv(cursor, step)
    run.restored = cursor
    run.garbage_uncomputed = run.restored == initial
    if not run.garbage_uncomputed:
        return Err(SeamError.verification_failed, "inverse(forward(x)) != x")

    run.measurement = measure_thermodynamic(
        technology,
        kernel,
        bits_erased=run.landauer_bits,
        switches=total_steps * 2,
        reversible=True,
    )
    return Ok(run)


def pebble_bounds(n_steps: int, levels: int) -> Tuple[int, int]:
    n = max(1, n_steps)
    k = max(1, levels)
    return k * (n - 1) + 1, (2 * n - 1) ** k

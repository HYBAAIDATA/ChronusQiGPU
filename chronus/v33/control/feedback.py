# feedback.py -- Closed-loop quantum control (Kalman estimate + pulse correction).
# Pure estimation + unitary feedback; no FPGA / ASIC claims.

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from .controller import QuantumController, Pulse
from ..academic.mit import MIT_FaultTolerant_Control


@dataclass
class FeedbackStep:
    measurement: float
    control_output: np.ndarray
    state_norm: float


class ClosedLoopController:
    """Estimate a classical pointer from weak readout, apply corrective pulse.

    Uses the existing MIT Kalman+PID filter on a 2-D error signal derived from
    the measurement residual, then maps the PID output to a pulse amplitude.
    """

    def __init__(self, n: int, hamiltonian: Optional[np.ndarray] = None, seed: int = 0):
        self.ctrl = QuantumController(n, hamiltonian=hamiltonian, seed=seed)
        self.filter = MIT_FaultTolerant_Control(state_dim=2, meas_dim=2)
        self.history: List[FeedbackStep] = []

    def step(self, target_expectation: float = 0.0, dt: float = 1e-3) -> FeedbackStep:
        meas = self.ctrl.readout(epsilon=0.02)
        z = np.array([meas.expectation or 0.0, 0.0])
        target = np.array([target_expectation, 0.0])
        out = self.filter.step(z, target, dt=dt)
        # Map first PID channel to a corrective x-pulse
        amp = float(np.clip(out[0], -2.0, 2.0))
        self.ctrl.apply_pulse(Pulse(duration=dt, amplitude=amp, phase=0.0))
        rec = FeedbackStep(
            measurement=float(meas.expectation or 0.0),
            control_output=out,
            state_norm=float(np.linalg.norm(self.ctrl.state)),
        )
        self.history.append(rec)
        return rec


def _self_test() -> str:
    cl = ClosedLoopController(n=8)
    for _ in range(15):
        cl.step(target_expectation=0.5)
    assert len(cl.history) == 15
    assert all(abs(h.state_norm - 1.0) < 1e-8 for h in cl.history)
    return "control.feedback._self_test: PASS"


if __name__ == "__main__":
    print(_self_test())

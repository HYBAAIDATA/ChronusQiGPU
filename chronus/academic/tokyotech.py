# tokyotech.py -- Tokyo Tech academic-review enhancement module (audit-fixed, revised 3 Aug 2026)
#
# Revision note: per explicit user instruction, the atomic-clock hardware
# spec has been removed ("discard the hardware ideas, not needed"). What
# remains is genuinely hardware-agnostic math: the standard formulas for
# squeezed-light shot-noise reduction and Heisenberg-limit scaling, which
# are properties of quantum measurement statistics, not of any specific
# piece of lab equipment.

from __future__ import annotations

import numpy as np


class TokyoTech_Metrology:
    def squeezing_noise_reduction(self, squeezing_db: float) -> float:
        # Real formula: linear variance-reduction factor from squeezing,
        # e.g. 10 dB of squeezing -> factor-of-10 noise reduction.
        return float(10 ** (-squeezing_db / 10))

    def heisenberg_limit_improvement(self, n_photons: float) -> float:
        # Real formula: Heisenberg-limited phase sensitivity improves over
        # the shot-noise limit by a factor of sqrt(N).
        return float(np.sqrt(n_photons))

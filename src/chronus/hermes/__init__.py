"""Hermes: the Chronus acceleration namespace.

chronus.hermes is the canonical import path for the bounded acceleration
modules. Their implementation currently lives in chronus.acceleration; the
module objects exported here are the same objects:

* chronus.hermes.fourier: bounded discrete Fourier transform of an explicit
  power-of-two vector.
* chronus.hermes.state: bounded state normalisation and unitary application.

Each module's docstring states its numerical contract and tolerance. Exact,
zero-rounding Fourier and phase-estimation routines belong to TURING
(turing.algorithms); Hermes does not re-implement exact cyclotomic arithmetic.
"""

import sys

from chronus.acceleration import fourier, state

sys.modules[__name__ + ".fourier"] = fourier
sys.modules[__name__ + ".state"] = state

__all__ = ["fourier", "state"]

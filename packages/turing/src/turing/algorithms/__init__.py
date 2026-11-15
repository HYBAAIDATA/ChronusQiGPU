"""Exact evaluation of standard quantum algorithms over cyclotomic fields.

Every amplitude is an exact element of Q(zeta_n) (or of Q for the Hadamard
algorithms), every probability is an exact rational or cyclotomic number, and
every reduction of a state is a lossless folding by symmetry. There is no
floating point, no rounding and no randomness. Modules:

* :mod:`.oracles` - the oracle protocol (``domain_size`` plus ``__call__``)
* :mod:`.walsh`, :mod:`.gf2` - exact Walsh-Hadamard transforms and GF(2) algebra
* :mod:`.deutsch_jozsa`, :mod:`.bernstein_vazirani`, :mod:`.simon`
* :mod:`.grover` - folded and unfolded Grover iterations
* :mod:`.qft`, :mod:`.qpe`, :mod:`.shor`
* :mod:`.clifford` - stabilizer tableau; :mod:`.structured` - 2,500-qubit paths
"""

from . import (
    bernstein_vazirani,
    clifford,
    deutsch_jozsa,
    gf2,
    grover,
    oracles,
    qft,
    qpe,
    shor,
    simon,
    structured,
    walsh,
)
from .clifford import CliffordCircuit, PauliOperator, StabilizerTableau, ghz_circuit
from .gf2 import AffineSubspace
from .oracles import AffineOracle, BooleanOracle, FunctionOracle, LinearOracle, Oracle

__all__ = [
    "AffineOracle",
    "AffineSubspace",
    "BooleanOracle",
    "CliffordCircuit",
    "FunctionOracle",
    "LinearOracle",
    "Oracle",
    "PauliOperator",
    "StabilizerTableau",
    "bernstein_vazirani",
    "clifford",
    "deutsch_jozsa",
    "ghz_circuit",
    "gf2",
    "grover",
    "oracles",
    "qft",
    "qpe",
    "shor",
    "simon",
    "structured",
    "walsh",
]

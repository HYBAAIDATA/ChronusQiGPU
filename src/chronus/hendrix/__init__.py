"""Hendrix: exact structured-search primitives for Chronus.

Hendrix (``chronus.hendrix``) provides exactly four things.

1. ``PrimeField`` and ``GF257`` (``chronus.hendrix.galois``): exact arithmetic
   in a prime field F_p with ``p <= MAX_FIELD_ORDER`` (2**20) through
   discrete-logarithm tables. The EXP/LOG tables are built once, in O(p) time
   and memory, from the smallest primitive root, whose order is verified in
   code. Afterwards ``mul``, ``div``, ``inverse``, ``pow``, ``discrete_log``,
   ``antilog`` and ``zech_log`` each cost a fixed number of table reads.
   ``GF257`` is F_257: generator 3, multiplicative group order 256 = 2**8.
2. Oracle objects (``chronus.hendrix.oracles``) for search and
   period-finding algorithms, following the shared oracle protocol: an int
   ``domain_size`` and ``__call__(x) -> int`` for ``0 <= x < domain_size``;
   Boolean oracles return 0 or 1. ``is_oracle`` checks the protocol by duck
   typing; ``turing`` is not imported.
3. ``chronus.hendrix.structured``: a facade that re-exports, unchanged, the
   existing closed-form F_257 phase routines (``chronus.math.f257_search``)
   and the legacy finite-field search iterates (``chronus.quantum``), with a
   one-line description of what each one computes in ``structured.CATALOG``.
   It is imported explicitly; importing ``chronus.hendrix`` does not load the
   legacy ``chronus.quantum`` namespace.
4. ``chronus.hendrix.locate``: the Galois locator. For oracles whose condition
   is algebraic over F_p (discrete log, multiplicative order, polynomial
   roots, square roots, GF(2)-linear hidden period) it computes the marked
   inputs from the algebra, with no answer table and no scan, for any prime p,
   and confirms each one by querying the oracle. It is imported explicitly.

Hendrix uses exact integer arithmetic only. ``PrimeField`` refuses fields above
2**20. The locator works table-free in larger fields; its discrete logarithm
is Pohlig-Hellman, so it is fast only when the group order factors into small
primes (it refuses otherwise) and is no shortcut for groups chosen to resist
it. Oracles without algebraic structure (for example SHA-256d target
membership) are refused, not scanned. Hendrix is not part of TURING and does
not model physical quantum systems.
"""

from chronus.hendrix.galois import GF257, MAX_FIELD_ORDER, PrimeField
from chronus.hendrix.oracles import (
    MAX_PROMISE_CHECK_BITS,
    DiscreteLogOracle,
    PeriodOracle,
    QuadraticResidueElementOracle,
    QuadraticResidueOracle,
    XorPeriodOracle,
    is_oracle,
)

__all__ = [
    "DiscreteLogOracle",
    "GF257",
    "MAX_FIELD_ORDER",
    "MAX_PROMISE_CHECK_BITS",
    "PeriodOracle",
    "PrimeField",
    "QuadraticResidueElementOracle",
    "QuadraticResidueOracle",
    "XorPeriodOracle",
    "is_oracle",
]

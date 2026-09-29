"""MLA1517 reference runtime — exact constants shared by every module.

No floats. Every value here is an exact integer, an exact algebraic pair, or
an exact square root. The ``no_float_in_math_core`` release gate scans this
package and rejects any float literal or ``float()``/``complex()`` call, so
these constants are the whole numeric vocabulary of the core.

Golden ratio identities, exact:

    phi = (1 + sqrt5) / 2
    phi^2 = phi + 1
    1/phi = phi - 1 = (sqrt5 - 1) / 2
    sqrt5 = 2*phi - 1

The cube-root constants are represented as the minimal polynomials they
satisfy, because their closed forms involve cube roots that this exact core
deliberately does not evaluate in floating point.
"""

from __future__ import annotations

from lucas.ladder import SCALE_RUNGS as _CANONICAL_SCALE_RUNGS

# --------------------------------------------------------------------------
# Exact integer recurrence ladder
# --------------------------------------------------------------------------

#: The hardware-scaling dial. lucas/ladder.py is the single declaration of the
#: rungs; restating the tuple here would fork the contract.
SCALE_RUNGS: tuple[int, ...] = tuple(_CANONICAL_SCALE_RUNGS)

#: The first declared transition in the build programme.
FIRST_SOURCE_SCALE: int = 15
FIRST_TARGET_SCALE: int = 17

#: The declared ladder. Immutable; the scale controller rejects anything else.
#: It is the canonical rungs plus 17, because the build programme names
#: 15 -> 17 as the FIRST transition target, so a ladder without it would
#: refuse the programme's own first declared step.
LADDER: tuple[int, ...] = tuple(sorted({*SCALE_RUNGS, FIRST_TARGET_SCALE}))

#: Smallest target the consensus-permitted difficulty represents.
LOWEST_BITS: int = 0x1D00FFFF

#: The 11D descriptor is a fixed ABI size, asserted at import of state.py.
STATE_BYTES: int = 64

#: PRIME-DB vertex count: 20 dodecahedral memory nodes.
VERTEX_COUNT: int = 20

#: M32 execution fabric: 12 icosahedral + 20 dodecahedral sites.
M32_EXECUTION_NODES: int = 12
M32_MEMORY_NODES: int = 20
M32_SITES: int = M32_EXECUTION_NODES + M32_MEMORY_NODES

#: Logical work partitions over the M32 overlay.
PARTITION_COUNT: int = 32

# --------------------------------------------------------------------------
# Cassini seal
# --------------------------------------------------------------------------

#: L_n^2 - 5*F_n^2 = 4*(-1)^n
CASSINI_IDENTITY: str = "L_n^2 - 5*F_n^2 = 4*(-1)^n"

#: F_{n-1}F_{n+1} - F_n^2 = (-1)^n
CASSINI_STORAGE_SEAL: str = "F_{n-1}F_{n+1} - F_n^2 = (-1)^n"


def cassini_seal(n: int) -> int:
    """Expected seal for a Fibonacci state at index ``n``: +1 or -1.

    Exact integer, never 0. A state whose seal is 0 is invalid, not neutral.
    """
    if n < 0:
        raise ValueError("Fibonacci index must be non-negative")
    return 1 if n % 2 == 0 else -1


# --------------------------------------------------------------------------
# Exact algebraic constants, as minimal-polynomial descriptors
# --------------------------------------------------------------------------

#: name -> (minimal polynomial coefficients, constant term, discriminant)
ALGEBRAIC_FAMILIES: dict[str, tuple[tuple[int, ...], int, int]] = {
    # x^2 - x - 1 = 0  (golden ratio)
    "phi": ((-1, 1, 1), -1, 5),
    # x^3 - x - 1 = 0  (plastic constant)
    "rho": ((-1, 0, 1, 1), -1, -23),
    # x^3 - x^2 - 1 = 0  (supergolden ratio)
    "psi": ((-1, -1, 0, 1), -1, -23),
    # x^3 - x^2 - x - 1 = 0  (tribonacci constant)
    "tau": ((-1, -1, -1, 1), -1, -44),
}

#: Promoted recurrences. Each maps a name to (order, initial values).
RECURRENCE_FAMILIES: dict[str, tuple[int, tuple[int, ...]]] = {
    "fibonacci": (2, (0, 1)),
    "padovan": (3, (1, 1, 1)),
    "narayana": (3, (0, 1, 1)),
    "tribonacci": (3, (0, 0, 1)),
}

__all__ = [
    "ALGEBRAIC_FAMILIES",
    "CASSINI_IDENTITY",
    "CASSINI_STORAGE_SEAL",
    "FIRST_SOURCE_SCALE",
    "FIRST_TARGET_SCALE",
    "LADDER",
    "LOWEST_BITS",
    "M32_EXECUTION_NODES",
    "M32_MEMORY_NODES",
    "M32_SITES",
    "PARTITION_COUNT",
    "RECURRENCE_FAMILIES",
    "SCALE_RUNGS",
    "STATE_BYTES",
    "VERTEX_COUNT",
    "cassini_seal",
]

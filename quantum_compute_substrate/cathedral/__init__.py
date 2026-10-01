"""Cathedral of the Greats.

The founding minds of quantum theory, computation, and information --
re-expressed in the substrate formalism, with 2026 elevation.

Each module gives the honoree's core mathematical construct, made concrete,
testable, and integrated with the rest of the substrate.

This is not a museum. Every function here is used somewhere in the substrate.
"""

from dataclasses import dataclass
from typing import List

from . import (
    schrodinger,
    heisenberg,
    dirac,
    pauli,
    von_neumann,
    einstein,
    bell,
    feynman,
    turing,
    shannon,
    landauer,
    deutsch,
)


@dataclass(frozen=True)
class Great:
    name: str
    born: int
    died: int  # 0 if living
    contribution: str
    module: str


GREATS: List[Great] = [
    Great("Erwin Schrodinger", 1887, 1961, "Wave mechanics and entanglement", "schrodinger"),
    Great("Werner Heisenberg", 1901, 1976, "Uncertainty and matrix mechanics", "heisenberg"),
    Great("Paul Dirac", 1902, 1984, "Relativistic quantum mechanics and bra-ket", "dirac"),
    Great("Wolfgang Pauli", 1900, 1958, "Spin, exclusion, and Pauli algebra", "pauli"),
    Great("John von Neumann", 1903, 1957, "Density matrix, entropy, measurement", "von_neumann"),
    Great("Albert Einstein", 1879, 1955, "EPR paradox and non-locality", "einstein"),
    Great("John Bell", 1928, 1990, "Bell inequalities and Tsirelson bound", "bell"),
    Great("Richard Feynman", 1918, 1988, "Path integrals and quantum simulation", "feynman"),
    Great("Alan Turing", 1912, 1954, "Universal computation and undecidability", "turing"),
    Great("Claude Shannon", 1916, 2001, "Information theory and channel capacity", "shannon"),
    Great("Rolf Landauer", 1927, 1999, "Thermodynamic cost of computation", "landauer"),
    Great("David Deutsch", 1953, 0, "Universal quantum computer", "deutsch"),
]


def list_greats() -> List[Great]:
    return list(GREATS)


def find(name: str) -> Great:
    for g in GREATS:
        if g.name.lower() == name.lower() or g.module == name.lower():
            return g
    raise KeyError(name)


__all__ = [
    "Great",
    "GREATS",
    "list_greats",
    "find",
    "schrodinger",
    "heisenberg",
    "dirac",
    "pauli",
    "von_neumann",
    "einstein",
    "bell",
    "feynman",
    "turing",
    "shannon",
    "landauer",
    "deutsch",
]

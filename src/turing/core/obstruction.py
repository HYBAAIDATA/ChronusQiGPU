"""
Turing Exact Quantum Library — Formal Obstruction Primitive
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Obstruction:
    """
    Formal witness of an algebraic or continuous obstruction.
    Returned when an operation cannot be closed within the requested discrete ring.
    """
    primitive: str
    value: str
    ring: str
    message: str

    def __repr__(self) -> str:
        return f"Obstruction(primitive='{self.primitive}', value='{self.value}', ring='{self.ring}')"

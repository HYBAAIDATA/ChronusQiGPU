"""
Turing Exact Quantum Library — Error Hierarchy
"""

class TuringError(Exception):
    """Base exception for all errors in the Turing algebraic quantum library."""
    pass


class RingError(TuringError):
    """Raised when an operation violates exact ring arithmetic or leaves the ring."""
    pass


class NonUnitError(RingError):
    """Raised when inversion is attempted on an element that is not a unit in Z[zeta_p]."""
    pass


class DimensionMismatchError(TuringError, ValueError):
    """Raised when matrix or vector dimensions are incompatible."""
    pass


class StateNormError(TuringError, ValueError):
    """Raised when a quantum state has zero norm or invalid normalization."""
    pass


class AlgebraicObstructionError(TuringError):
    """Raised when a continuous or out-of-ring operation is attempted without a projective or field lift."""
    pass

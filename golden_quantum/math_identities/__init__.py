"""
Mathematical identities module — d'Ocagne, Honsberger, Fibonacci/Lucas polynomials.

These extend the golden-ratio family with cross-index and polynomial generalizations.
"""

from .docagne import docagne_identity, docagne_distance, fib_signed
from .honsberger import honsberger_identity, honsberger_compose
from .polynomials import (
    fib_poly_coeffs, lucas_poly_coeffs,
    fib_poly_eval, lucas_poly_eval,
    fib_poly_specialization, lucas_poly_specialization,
    lucas_fib_relation,
)

__all__ = [
    "docagne_identity", "docagne_distance", "fib_signed",
    "honsberger_identity", "honsberger_compose",
    "fib_poly_coeffs", "lucas_poly_coeffs",
    "fib_poly_eval", "lucas_poly_eval",
    "fib_poly_specialization", "lucas_poly_specialization",
    "lucas_fib_relation",
]

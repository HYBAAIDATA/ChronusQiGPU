"""QSDL scene language — recovered canonical grammar + compiler (HYBA Data).

Recovered from owner-disk archives Nov 2026; promoted as the single
canonical pair after 7-copy dedupe (see `recovery_merge/README.md`):
compiler `backend/chronos/qsdl_compiler.py` (v3.0 real BNF-grammar pass,
hash `802AA6EA…`), parser from chronos-one-igpu-v3.4 (`qsdl_parser.py`),
plus the compiler's sibling `manifold.py` (hash-pinned in the ledger).
Legacy label call sites (`render(scene="default")`,
`phi_tier_{power}`) resolve to the fixed canonical scene for
byte-identical reproduction — that is compatibility behavior, not a
grammar claim. The Chronos ONE v3.4 lineage is a separate historical
graphics path; QSDL integration into the Chronus execution plane remains
NOT PORTED until wired with tests.
"""

from chronus.qsdl.manifold import M32Manifold
from chronus.qsdl.qsdl_compiler import (
    ManifoldConfig,
    QScene,
    QSDLCompileError,
    QSDLCompiler,
)
from chronus.qsdl.qsdl_parser import (
    QSDLSyntaxError,
    parse_qsdl,
)

__all__ = [
    "M32Manifold",
    "ManifoldConfig",
    "QSDLCompileError",
    "QSDLCompiler",
    "QSDLSyntaxError",
    "QScene",
    "parse_qsdl",
]

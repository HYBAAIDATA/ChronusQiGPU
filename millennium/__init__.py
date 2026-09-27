"""millennium — the Clay Millennium Prize problem surface of PYTHIA.

Consolidates every Millennium-related implementation in this repository into
one importable package.  The seven Clay problems are covered by deterministic
probes in :mod:`millennium.millennium_suite`:

    RH     Riemann Hypothesis
    PNP    P versus NP
    YM     Yang-Mills existence and mass gap
    NS     Navier-Stokes existence and smoothness
    BSD    Birch and Swinnerton-Dyer conjecture
    HODGE  Hodge conjecture
    POINC  Poincare conjecture (RESOLVED — Perelman 2002/2003)

Honesty invariant: no component of this package may label a Clay problem
ESTABLISHED.  Every result carries an evidence class and a declared scope;
``MillenniumSuite.assert_no_established()`` enforces the invariant.

Modules
-------
millennium_suite            flagship 7-problem deterministic probe harness
mathematical_discovery      PYTHIA discovery engine (suite payload consumer)
nobel_fields_intelligence   6-problem phi-scaling exploration module
yang_mills_data             SU(n) Lie algebra / golden transform / spectral
                            geometry / persistent homology substrate
poincare_cassini_search     Poincare-Cassini search over the manifold
poincare_golden_11d         golden 11D manifold construction
hyba_poincare_yangmills     finite 2I / Poincare-homology Yang-Mills thread
millennium_reasoning_service  FastAPI endpoints over the reasoning engines
sl5_millennium_bridge       SL(5,Z) Yang-Mills / Riemann structural tracks
clay_checklist              Yang-Mills honesty layer (C1-C10 / G1-G6)
hodge_bridge.ts             TypeScript Hodge bridge (Zeckendorf substrate)
rtl/yang_mills_gap_monitor.sv  SystemVerilog gap monitor
docs/OPEN_SCIENTIFIC_PROBLEMS_LEDGER.md

Usage
-----
    >>> from millennium import MillenniumSuite
    >>> suite = MillenniumSuite(scale="quick")
    >>> report = suite.run()
    >>> suite.assert_no_established(report)

or from the CLI::

    python -m millennium.millennium_suite --scale quick
"""

from .millennium_suite import (
    BSD_CURVES,
    EVIDENCE_CLASSES,
    EXACT_ARITHMETIC,
    FINITE_RANGE_OBSERVATION,
    FINITE_VOLUME_VERIFIED,
    KNOWN_THEOREM_SCOPE,
    MILLENNIUM_PROBLEMS,
    OPEN,
    SCALE_BUDGETS,
    TRUNCATED_MODEL,
    ZETA_ZERO_GAMMAS,
    MillenniumProblem,
    MillenniumSuite,
    main as suite_main,
    probe_bsd,
    probe_hodge,
    probe_navier_stokes,
    probe_p_vs_np,
    probe_poincare,
    probe_riemann,
    probe_yang_mills,
)

# Optional submodules carry heavier dependencies (sympy, scipy, networkx,
# fastapi, or repo-internal packages).  They are resolved lazily so that
# ``import millennium`` never fails on a missing optional dependency.
_LAZY_SUBMODULES = {
    "mathematical_discovery",
    "nobel_fields_intelligence",
    "yang_mills_data",
    "poincare_cassini_search",
    "poincare_golden_11d",
    "hyba_poincare_yangmills",
    "hyba_golden_mass_gap",
    "millennium_reasoning_service",
    "sl5_millennium_bridge",
    "clay_checklist",
}


def __getattr__(name: str):
    if name in _LAZY_SUBMODULES:
        import importlib

        module = importlib.import_module(f".{name}", __name__)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BSD_CURVES",
    "EVIDENCE_CLASSES",
    "EXACT_ARITHMETIC",
    "FINITE_RANGE_OBSERVATION",
    "FINITE_VOLUME_VERIFIED",
    "KNOWN_THEOREM_SCOPE",
    "MILLENNIUM_PROBLEMS",
    "OPEN",
    "SCALE_BUDGETS",
    "TRUNCATED_MODEL",
    "ZETA_ZERO_GAMMAS",
    "MillenniumProblem",
    "MillenniumSuite",
    "suite_main",
    "probe_bsd",
    "probe_hodge",
    "probe_navier_stokes",
    "probe_p_vs_np",
    "probe_poincare",
    "probe_riemann",
    "probe_yang_mills",
]

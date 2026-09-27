"""
Millennium Reasoning API Service
================================

FastAPI endpoints for Millennium Prize Problem exploration, backed by the
real deterministic probes in :mod:`millennium.millennium_suite`.

Every endpoint runs the shipped probe implementation — exact prime counts
vs li(x)/R(x), measured DPLL cost on seeded 3-SAT, the de-aliased
pseudo-spectral Navier-Stokes truncation, the finite-volume SU(2) covariant
Laplacian spectrum, exact Hasse-bound verification and the BSD product law,
Hodge-diamond arithmetic, and the discrete conformal curvature flow on S^2.

No endpoint proves anything: every response carries the probe's evidence
class, declared scope, and ``proof_claim = False``.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

try:
    from .millennium_suite import (
        EVIDENCE_CLASSES,
        MILLENNIUM_PROBLEMS,
        SCALE_BUDGETS,
        MillenniumSuite,
    )
except ImportError:  # pragma: no cover - direct script use
    from millennium_suite import (
        EVIDENCE_CLASSES,
        MILLENNIUM_PROBLEMS,
        SCALE_BUDGETS,
        MillenniumSuite,
    )

logger = logging.getLogger("hyba.millennium_api")

router = APIRouter(prefix="/millennium", tags=["Millennium Reasoning"])

_DEFAULT_SCALE = os.environ.get("MILLENNIUM_SCALE", "standard")
_suites: Dict[str, MillenniumSuite] = {}


def _get_suite(scale: Optional[str] = None) -> MillenniumSuite:
    """Lazily build (and cache) a suite per declared scale."""
    scale = scale or _DEFAULT_SCALE
    if scale not in _suites:
        _suites[scale] = MillenniumSuite(scale=scale)
    return _suites[scale]


def _budget_overrides(problem_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Pass through numeric overrides, clamped at the declared `deep` budget.

    Probes are deterministic and finite; the clamp keeps a request from
    silently exceeding the largest declared workload.
    """
    spec = next(p for p in MILLENNIUM_PROBLEMS if p.id == problem_id)
    deep = SCALE_BUDGETS["deep"]
    overrides: Dict[str, Any] = {}
    for key in spec.budget_keys:
        value = params.get(key)
        if value is None:
            continue
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=422, detail=f"{key} must be an integer, got {value!r}"
            )
        overrides[key] = min(numeric, int(deep[key]))
    return overrides


def _run(problem_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Run one real probe with bounded overrides and return the honest result."""
    scale = params.get("scale") or _DEFAULT_SCALE
    if scale not in SCALE_BUDGETS:
        raise HTTPException(
            status_code=422,
            detail=f"unknown scale {scale!r}; expected one of {sorted(SCALE_BUDGETS)}",
        )
    overrides = _budget_overrides(problem_id, params)
    result = _get_suite(scale).probe(problem_id, **overrides)
    logger.info(
        "millennium probe %s scale=%s evidence=%s", problem_id, scale, result["evidence_class"]
    )
    return result


@router.post("/p_vs_np/analyze")
async def analyze_complexity(workload: Dict[str, Any]) -> Dict[str, Any]:
    """P vs NP: measured DPLL node counts on deterministic seeded 3-SAT at the
    4.26 phase ratio. A finite cost window separates nothing."""
    try:
        return _run("p_vs_np", workload)
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover - defensive boundary
        logger.error("P vs NP probe error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/riemann/predict_primes")
async def predict_prime_distribution(interval: Dict[str, Any]) -> Dict[str, Any]:
    """Riemann: exact prime counts vs li(x) and the Gram-series R(x), plus the
    explicit formula with the first 20 non-trivial zero pairs."""
    try:
        return _run("riemann", interval)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Riemann probe error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/yang_mills/gap")
async def yang_mills_gap(field_state: Dict[str, Any]) -> Dict[str, Any]:
    """Yang-Mills: exact spectrum of the 4D finite-volume covariant Laplacian
    with deterministic SU(2) links. Positive finite-volume gap is a box
    artefact, not a continuum mass gap."""
    try:
        return _run("yang_mills", field_state)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Yang-Mills probe error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/navier_stokes/predict_flow")
async def predict_flow_dynamics(state: Dict[str, Any]) -> Dict[str, Any]:
    """Navier-Stokes: de-aliased pseudo-spectral Galerkin truncation of the 3D
    incompressible system with RK4 — vorticity, enstrophy, BKM integral."""
    try:
        return _run("navier_stokes", state)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Navier-Stokes probe error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bsd/rank")
async def bsd_probe(params: Dict[str, Any]) -> Dict[str, Any]:
    """BSD: exact Hasse-bound verification per prime and the classical
    prod(N_p/p) growth law against literature-supplied ranks."""
    try:
        return _run("bsd", params)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("BSD probe error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hodge/analyze_topology")
async def analyze_topology(manifold: Dict[str, Any]) -> Dict[str, Any]:
    """Hodge: exact Hodge-diamond arithmetic for complex tori, Betti numbers,
    Euler characteristics, and the count of Hodge classes the classical
    Lefschetz (1,1) theorem does not reach."""
    try:
        return _run("hodge", manifold)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Hodge probe error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/poincare/flow")
async def poincare_flow(sphere: Dict[str, Any]) -> Dict[str, Any]:
    """Poincare (RESOLVED — Perelman): discrete conformal curvature flow on a
    triangulated S^2; Gauss-Bonnet identity and curvature-spread reduction."""
    try:
        return _run("poincare", sphere)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Poincare probe error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/aggregate")
async def aggregate_millennium_report(request: Dict[str, Any]) -> Dict[str, Any]:
    """Run every probe at the requested scale and return the aggregate report.

    Body may carry ``scale`` (quick|standard|deep) and an optional ``only``
    list of problem ids. Enforces ``assert_no_established()`` on the result.
    """
    try:
        scale = request.get("scale") or _DEFAULT_SCALE
        if scale not in SCALE_BUDGETS:
            raise HTTPException(
                status_code=422,
                detail=f"unknown scale {scale!r}; expected one of {sorted(SCALE_BUDGETS)}",
            )
        only = request.get("only")
        if only is not None and not isinstance(only, list):
            raise HTTPException(status_code=422, detail="only must be a list of problem ids")
        suite = _get_suite(scale)
        report = suite.run(only=only)
        suite.assert_no_established(report)
        logger.info(
            "millennium aggregate: %d problems, %d established",
            report["problems"],
            report["established_count"],
        )
        return report
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Millennium aggregate error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/problems")
async def list_problems() -> Dict[str, Any]:
    """Metadata for the seven Clay problems: statement, status, budget keys."""
    return {"problems": _get_suite().problems()}


@router.get("/inventory")
async def asset_inventory() -> Dict[str, Any]:
    """Where every millennium asset lives, and whether each is importable."""
    return {"assets": _get_suite().asset_inventory()}


@router.get("/info")
async def get_millennium_info() -> Dict[str, Any]:
    """Document the service: what runs, what it measures, what it is not."""
    return {
        "approach": "Deterministic probes over declared, seeded workloads",
        "philosophy": "Measure exactly, label the scope honestly, claim nothing",
        "probes": {p.id: p.name for p in MILLENNIUM_PROBLEMS},
        "scales": sorted(SCALE_BUDGETS),
        "evidence_classes": list(EVIDENCE_CLASSES),
        "default_scale": _DEFAULT_SCALE,
        "note": (
            "Every endpoint runs the shipped probe implementation and returns "
            "its evidence class and honest scope. No endpoint claims a proof "
            "of any Clay problem."
        ),
    }

"""Smoke tests for the deprecated chronos → chronus.v33 compatibility facade."""

from __future__ import annotations

import warnings

import numpy as np
import pytest


@pytest.mark.unit
def test_chronos_facade_reexports_v33_engine():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        import chronos

        from chronos import ChronosEngine, M32Manifold
        from chronus.v33 import ChronosEngine as V33Engine
        from chronus.v33 import M32Manifold as V33Manifold

    assert ChronosEngine is V33Engine
    assert M32Manifold is V33Manifold
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
    assert "ChronosEngine" in getattr(chronos, "__all__", [])


@pytest.mark.unit
def test_chronos_academic_facade_matches_v33():
    from chronos.academic import AcademicChronosEngine, Caltech_Ising_Anyons
    from chronus.v33.academic import (
        AcademicChronosEngine as V33AcademicEngine,
        Caltech_Ising_Anyons as V33Caltech,
    )

    assert Caltech_Ising_Anyons is V33Caltech
    assert AcademicChronosEngine is V33AcademicEngine


@pytest.mark.unit
def test_chronos_engine_submodule_import_path():
    """Backup-style path: from chronos.engine import ChronosEngine."""
    from chronos.engine import ChronosEngine
    from chronus.v33.engine import ChronosEngine as V33Engine

    assert ChronosEngine is V33Engine


@pytest.mark.unit
def test_facade_engine_render_smoke():
    """Minimal live call — proves facade points at real v3.3, not archived v2."""
    from chronos import ChronosEngine, M32Manifold

    engine = ChronosEngine()
    assert engine is not None
    assert M32Manifold is not None
    # Manifold state is deterministic maths (not the old random stub)
    m = M32Manifold()
    s = np.asarray(m.get_state(), dtype=np.complex128)
    assert s.ndim == 1
    assert s.shape[0] >= 1
    # Two calls must match (v1 random stub regression guard)
    s2 = np.asarray(m.get_state(), dtype=np.complex128)
    assert np.allclose(s, s2)


@pytest.mark.unit
def test_v33_render_pixel_contract_and_determinism():
    """Page/archive geometry contract + no RNG energy flicker.

    Archived sandbox energy (−7.337994) is historical evidence only; live v3.3
    may differ slightly after memory/mixer evolution. What must hold:
    8K hit counts, finite negative energy, bit-identical re-render.
    """
    from chronus.v33 import ChronosEngine

    engine = ChronosEngine()
    r1 = engine.render("default")
    r2 = engine.render("default")

    assert tuple(r1.frame_shape) == (4320, 7680, 3)
    assert r1.rendered_pixels_hit == 1_832_112
    assert r1.total_pixels == 33_177_600
    assert r1.energy == r2.energy
    assert np.isfinite(r1.energy)
    assert r1.energy < 0.0
    # Guard against the old hardcoded 0.123456 stub and wild drift
    assert -20.0 < r1.energy < -1.0

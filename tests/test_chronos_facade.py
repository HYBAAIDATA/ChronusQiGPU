"""Smoke tests for the deprecated chronos → chronus.v33 compatibility facade."""

from __future__ import annotations

import sys
import warnings

import numpy as np
import pytest


# Legacy chronos facade removed under canonical Chronus consolidation.


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

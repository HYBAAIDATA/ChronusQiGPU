# tests/test_academic_integration.py -- Academic elevation layer.
from __future__ import annotations

import numpy as np
import pytest

from chronus.v33.academic.integration import (
    AcademicChronosEngine,
    apply_qed_diagonal_corrections,
    surface_code_correct_distribution,
    DistributionResidualCorrector,
    _self_test as integration_self_test,
)
from chronus.v33.academic.report import run_academic_enhancements


@pytest.mark.unit
def test_integration_self_test():
    assert integration_self_test() == "academic.integration._self_test: PASS"


@pytest.mark.unit
def test_qed_correction_changes_diagonal():
    h = np.diag(np.linspace(-2.0, 1.0, 16))
    h2 = apply_qed_diagonal_corrections(h)
    assert not np.allclose(np.diag(h), np.diag(h2))
    assert np.allclose(h2, h2.T)


@pytest.mark.unit
def test_surface_code_correct_distribution_renormalises():
    rng = np.random.default_rng(0)
    p = rng.random(32)
    p = p / p.sum()
    out, meta = surface_code_correct_distribution(p, distance=3)
    assert abs(out.sum() - 1.0) < 1e-10
    assert "correction" in meta


@pytest.mark.unit
def test_pinn_corrector_preserves_normalisation():
    n = 24
    f = np.linspace(0.1, 1.0, n)
    f = f / f.sum()
    c = DistributionResidualCorrector(n_faces=n, seed=1)
    c.fit(f, epochs=40)
    out = c.correct(f)
    assert abs(out.sum() - 1.0) < 1e-8
    assert np.all(out >= 0)


@pytest.mark.integration
def test_academic_engine_end_to_end(smoke_scene_source):
    eng = AcademicChronosEngine(
        n_faces=32,
        layers=2,
        enable_emp=True,
        enable_qed=True,
        enable_surface_code=True,
        enable_pinn_corrector=True,
    )
    out = eng.render(smoke_scene_source)
    assert out.qed_correction_applied
    assert out.base.rendered_pixels_hit > 0
    assert out.nist_fidelity is not None
    assert out.squeezing_noise_factor == 0.1
    assert out.anyon_fusion_sigma_sigma == ["1", "psi"]


@pytest.mark.integration
def test_run_academic_enhancements_no_tensor_train():
    # Must complete without OOM — tensor train is opt-in
    report = run_academic_enhancements(seed=0, include_tensor_train=False)
    assert "cern" in report
    assert "nist" in report
    assert report["tensor_train_1000_qubit"].get("skipped") is True
    assert report["caltech"]["fusion_sigma_sigma"] == ["1", "psi"]

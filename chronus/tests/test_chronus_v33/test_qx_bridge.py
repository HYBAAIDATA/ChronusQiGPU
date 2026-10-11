from __future__ import annotations

from chronus.production import STARTUP_QSDL
from chronus.v33.qx_bridge import compile_qsdl_to_qx, execute_qsdl_qx_reference


def test_real_qsdl_compiles_to_sealed_qx_and_executes():
    compiled = compile_qsdl_to_qx(STARTUP_QSDL, n_faces=32)
    assert compiled.buffer.sealed is True
    assert compiled.dimension == 32
    assert len(compiled.command_digest) == 64

    report = execute_qsdl_qx_reference(STARTUP_QSDL, n_faces=32)
    assert report["passed"] is True
    assert report["compilation"]["command_digest"] == report["execution"]["command_digest"]
    assert report["execution"]["backend"] == "chronus.qx.reference"
    assert report["execution"]["dimension"] == 32
    assert report["execution"]["norm_error"] <= 1e-10

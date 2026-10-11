from __future__ import annotations

import pytest

from chronus.production import ChronusMode, ChronusProductionRuntime, verify_startup_report
from chronus.virtual_igpu.adapters import ChronusSoftwareFabricAdapter


@pytest.mark.unit
def test_independent_mode_is_a_real_chronus_mode_without_physical_gpu(tmp_path):
    runtime = ChronusProductionRuntime(tmp_path / "independent")
    try:
        report = runtime.startup_voyage()
        verdict = verify_startup_report(report)
        assert verdict["passed"] is True
        assert report["mode"] == ChronusMode.INDEPENDENT.value
        assert report["physical_gpu_required"] is False
        assert report["execution"]["actual_adapter_id"] == "chronus-software-fabric"
        assert report["execution"]["verification"] == "match"
        assert report["math_pipeline"]["passed"] is True
        assert report["qx_pipeline"]["passed"] is True
        assert report["hardware_claimed"] is False
    finally:
        runtime.stop()


@pytest.mark.unit
def test_scale_stack_mode_fails_closed_without_a_physical_adapter(tmp_path):
    runtime = ChronusProductionRuntime(
        tmp_path / "scale",
        mode=ChronusMode.SCALE_STACK,
        adapters=[ChronusSoftwareFabricAdapter()],
    )
    try:
        with pytest.raises(Exception, match="accelerator|adapter"):
            runtime.startup_voyage()
    finally:
        runtime.stop()

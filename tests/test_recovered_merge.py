"""Recovered-module regression: QSDL grammar, benchmark record, provenance.

Provenance: owner-disk ZIPs staged under recovery_merge/ (see
recovery_merge/README.md for hashes and dedupe verdicts). These tests
pin the payable behavior — real parse, honest benchmark shape,
no engine wiring for reference-only modules — not the archives' prose.
"""

import json
import re
from pathlib import Path

from chronus.qsdl.qsdl_compiler import QSDLCompiler
import pytest

pytestmark = pytest.mark.real

RECOVERED = Path(__file__).resolve().parents[1] / "benchmarks" / "recovered"


def test_qsdl_real_grammar_parses_scene():
    scene = QSDLCompiler().compile(
        "scene sunset { camera { position = (0, 0, 5) } }"
    )
    assert type(scene).__name__ == "QScene"


def test_qsdl_legacy_label_still_resolves():
    first = QSDLCompiler().compile("phi_tier_10")
    second = QSDLCompiler().compile("phi_tier_10")
    assert type(first).__name__ == type(second).__name__ == "QScene"


def test_lucas_benchmark_record_shape_and_provenance():
    record = json.loads(
        RECOVERED.joinpath("lucas_results.json").read_text()
    )
    assert record["commit_sha"] == "UNVERSIONED-WORKTREE"
    for batch in record["batches"]:
        assert batch["seconds"] > 0 and batch["records"] > 0
        assert abs(
            batch["us_per_record"]
            - batch["seconds"] / batch["records"] * 1e6
        ) < 1e-6
    assert any("us_per_record" in line for line in record["limitations"])
    assert any(
        "Virtual device; no accelerator present or required" in line
        for line in record["limitations"]
    )


def test_8k_benchmark_record_promoted_with_scope():
    record = json.loads(
        RECOVERED.joinpath("results.json").read_text()
    )
    assert record["promotion"]["status"] == "RECOVERED_MEASURED"
    assert record["promotion"]["device"] == "virtual-device-by-design"
    render32 = record["full_render_at_scale"]["32"]
    assert render32["total_pixels"] == 7680 * 4320
    assert render32["energy"] == -7.337994
    assert render32["rendered_pixels_hit"] == 1832112
    measured = [t for t in record["phi_power_scaling"]["tiers"] if t["measured"]]
    projected = [t for t in record["phi_power_scaling"]["tiers"] if not t["measured"]]
    assert len(measured) == 3 and len(projected) == 2


def test_promoted_records_stay_commit_unbound():
    """Promotion is not re-measurement: these fields must never drift to 'current'."""
    for name in ("lucas_results.json", "results.json"):
        promotion = json.loads(RECOVERED.joinpath(name).read_text())["promotion"]
        assert promotion["status"] == "RECOVERED_MEASURED", name
        assert promotion["bound_to_commit"] is None, name
        assert promotion["re_measured_on_head"] is False, name
        assert promotion["source_archive"] == "chronos-one-igpu-v3.4", name
        assert re.fullmatch(r"[0-9a-f]{64}", promotion["source_archive_sha256"]), name


def test_recovered_reference_modules_not_imported_by_engine():
    import chronus.tensor as tensor

    for name in ("geodesic_tensor_engine", "quantum_formalism"):
        assert not hasattr(tensor, name), name

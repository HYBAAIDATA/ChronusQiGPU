from __future__ import annotations

import json
from pathlib import Path
from fractions import Fraction

from scripts.lucas_scale_matrix import (
    LucasScaleMatrixEngine,
    ScalingDomainSpec,
    exact_lucas_fibonacci,
)


def test_fast_doubling_exact_extended_ladder():
    expected = {7: 29, 10: 123, 12: 322, 15: 1364, 18: 5778, 20: 15127,
                31: 3010349, 50: 28143753123, 76: 7639424778862807}
    for n, value in expected.items():
        assert exact_lucas_fibonacci(n)[0] == value


def test_composite_lucas_identities():
    engine = LucasScaleMatrixEngine()
    assert engine.compose_domains("search", "memory", "add") == exact_lucas_fibonacci(22)[0]
    assert engine.compose_domains("search", "memory", "subtract") == exact_lucas_fibonacci(2)[0]
    assert engine.compose_domains("hardware_extended", "base_pattern", "add") == exact_lucas_fibonacci(38)[0]


def test_alignment_and_exact_rational_multiplier():
    spec = ScalingDomainSpec("aligned", 10, alignment_bytes=64, multiplier=Fraction(3, 2))
    capacity = spec.compute_capacity()
    assert capacity % 64 == 0
    assert capacity >= (123 * 3) // 2


def test_manifest_fingerprint_and_workload_validation():
    engine = LucasScaleMatrixEngine()
    manifest = engine.generate_matrix_manifest()
    fingerprint = engine.compute_fingerprint()
    assert engine.verify_workload_fingerprint(manifest, fingerprint)
    manifest["domain_capacities"]["memory"]["computed_capacity"] += 64
    assert not engine.verify_workload_fingerprint(manifest, fingerprint)


def test_config_file_contains_extended_domains():
    raw = json.loads(Path("configs/lucas_scale_matrix.example.json").read_text())
    engine = LucasScaleMatrixEngine.from_config(raw)
    indices = {spec.recurrence_index for spec in engine.domains.values()}
    assert {7, 31, 50, 76}.issubset(indices)

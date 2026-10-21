from __future__ import annotations

import json
from pathlib import Path

from scripts.benchmark_harness import BenchmarkHarness
from scripts.verify import verify_artifact, verify_composite_fingerprint

SEED = bytes.fromhex("11" * 32)


def test_full_pipeline_three_seals(tmp_path: Path):
    artifact = BenchmarkHarness(SEED, nonce_bits=8, target_prefix_bytes=1, trials=1).run("integration")
    assert artifact["verification"]["all_verified"]
    assert verify_artifact(artifact)
    assert verify_composite_fingerprint(artifact)
    path = tmp_path / "artifact.json"
    path.write_text(json.dumps(artifact), encoding="utf-8")
    assert verify_artifact(json.loads(path.read_text(encoding="utf-8")))


def test_composite_tamper_detected():
    artifact = BenchmarkHarness(SEED, nonce_bits=8, target_prefix_bytes=1, trials=1).run("tamper")
    artifact["fingerprints"]["matrix_sha256"] = "00" * 32
    assert not verify_composite_fingerprint(artifact)

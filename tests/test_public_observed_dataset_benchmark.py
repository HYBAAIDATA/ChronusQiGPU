"""Real observational dataset contract tests; no generated numerical samples.

Requires optional scikit-learn==1.8.0; skipping is NOT production evidence.
This verifies maintained source functions against SHA-pinned public inputs,
not current hardware performance, third-party attestation or deployment.
"""
from __future__ import annotations

import hashlib
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import numpy as np
import pytest
import yaml

from chronus.pulvini import fold_verified, unfold_verified
from chronus.tensor.folded_state import ExactFoldState
from chronus.tensor.geodesic import PhiTensorCore

pytestmark = pytest.mark.real

sklearn = pytest.importorskip("sklearn")
if sklearn.__version__ != "1.8.0":
    pytest.skip("PINNED_PUBLIC_DATASET_UNAVAILABLE: requires scikit-learn==1.8.0",
                allow_module_level=True)

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/benchmarks/prepare_public_uci_data.py"
_SPEC = spec_from_file_location("chronus_public_inputs", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
_M = module_from_spec(_SPEC)
_SPEC.loader.exec_module(_M)


@pytest.fixture(scope="module")
def inputs(tmp_path_factory):
    root = tmp_path_factory.mktemp("observed-uci") / "verified"
    result = _M.prepare(root)
    assert result["input_data_generated"] is False
    manifest = yaml.safe_load((root / "manifest.yaml").read_text())
    assert manifest["schema"] == "chronus.real-workload-manifest/1"
    for source in manifest["data_sources"]:
        path = root / source["path"]
        assert source["source_class"] == "PUBLIC_OBSERVED_DATASET"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"]
        assert source["sha256"] == _M.PINNED[source["path"]]
    return root, manifest


@pytest.mark.parametrize("name", ["uci_digits.npy", "uci_wine.npy", "uci_breast_cancer.npy"])
def test_real_observed_tensor_numerical_fidelity_and_accounting(inputs, name):
    root, _ = inputs
    tensor = np.load(root / name, allow_pickle=False)
    state, receipt = fold_verified(tensor, depth=4)
    restored = unfold_verified(state, receipt=receipt)
    np.testing.assert_allclose(restored, tensor, rtol=1e-12, atol=1e-12)
    assert receipt.retained_bytes == receipt.folded_bytes + receipt.kernel_bytes
    assert receipt.relative_reconstruction_error < 1e-12


@pytest.mark.parametrize("name", ["uci_digits.npy", "uci_wine.npy", "uci_breast_cancer.npy"])
def test_real_observed_tensor_reference_backend(inputs, name):
    root, _ = inputs
    tensor = np.load(root / name, allow_pickle=False)
    result = PhiTensorCore().execute("add", tensor, tensor)
    assert result["backend"] == "numpy-reference"
    np.testing.assert_array_equal(result["output"], np.add(tensor, tensor))


@pytest.mark.parametrize("name", list(_M.PINNED))
def test_real_observed_file_bytes_exact(inputs, name):
    root, _ = inputs
    payload = (root / name).read_bytes()
    fold = ExactFoldState.from_bytes(payload)
    assert fold.unfold() == payload
    start = len(payload) // 2
    stop = min(len(payload), start + 64)
    assert fold.unfold_partial(start, stop) == payload[start:stop]


def test_missing_optional_dataset_not_relabelled_production(inputs):
    _, manifest = inputs
    assert all(s["source_class"] == "PUBLIC_OBSERVED_DATASET"
               for s in manifest["data_sources"])


def test_preparation_refuses_existing_destination(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    with pytest.raises(ValueError, match='must not already exist'):
        _M.prepare(tmp_path)


def test_component_runner_rejects_unpinned_names(tmp_path):
    path = Path(__file__).resolve().parents[1] / "scripts/benchmarks/run_public_uci_components.py"
    spec = spec_from_file_location("chronus_uci_components", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    from sklearn.datasets import load_wine
    sample = np.ascontiguousarray(load_wine().data, dtype=np.float64)
    payload_path = tmp_path / "fake_0.npy"
    np.save(payload_path, sample)
    content = payload_path.read_bytes()
    entries = []
    for i in range(4):
        filename = f"fake_{i}.npy"
        (tmp_path / filename).write_bytes(content)
        entries.append({"path": filename, "kind": "tensor",
                        "sha256": hashlib.sha256(content).hexdigest(),
                        "source_class": "PUBLIC_OBSERVED_DATASET"})
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(yaml.safe_dump({
        "schema": "chronus.real-workload-manifest/1",
        "data_sources": entries}), encoding="utf-8")
    with pytest.raises(ValueError, match="name, digest, type"):
        module.run(manifest)


def test_component_runner_preserves_exact_source_mapping():
    path = Path(__file__).resolve().parents[1] / "scripts/benchmarks/run_public_uci_components.py"
    spec = spec_from_file_location("chronus_uci_contract", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.PINNED_INPUTS == {
        name: (digest, "snapshot" if name.endswith(".snapshot") else "tensor")
        for name, digest in _M.PINNED.items()
    }


def test_component_runner_rejects_content_modified_under_pinned_name(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts/benchmarks/run_public_uci_components.py"
    spec = spec_from_file_location("chronus_uci_integrity", script)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    directory = tmp_path / "pinned"
    _M.prepare(directory)
    original = directory / "uci_digits.npy"
    payload = original.read_bytes()
    original.write_bytes(payload[:-1] + bytes((payload[-1] ^ 1,)))
    with pytest.raises(ValueError, match="input SHA-256 mismatch"):
        module.run(directory / "manifest.yaml")


# Measured real-public-input paired workload; no synthetic timing evidence.
def test_real_observed_wine_paired_verified_useful_work(inputs):
    from importlib.util import module_from_spec, spec_from_file_location
    script = Path(__file__).resolve().parents[1] / "scripts/benchmarks/run_public_uci_components.py"
    spec = spec_from_file_location("chronus_public_paired_runner", script)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    root, _ = inputs
    path = root / "uci_wine.npy"
    record = module._measure_source(path, _M.PINNED[path.name], "tensor", depth=4)
    m = record["matched_useful_work"]
    assert m["measured_pairs"] == 13
    assert m["direct_add_ns"]["count"] == m["fold_unfold_add_ns"]["count"] == 13
    assert m["same_result_within_tolerance"] is True
    assert m["fold_and_verification_in_timed_candidate"] is True
    assert m["candidate_backend"] == "numpy-reference"
    assert m["physical_or_quantum_advantage_claimed"] is False
    assert m["production_qualification"] == "UNVERIFIED"
    assert m["observed_speedup_direct_over_folded"] > 0


@pytest.mark.parametrize("repetitions,warmup", [(2, 0), (202, 0), (13, -1), (13, 21)])
def test_paired_benchmark_rejects_invalid_sample_policy(repetitions, warmup):
    from importlib.util import module_from_spec, spec_from_file_location
    script = Path(__file__).resolve().parents[1] / "scripts/benchmarks/run_public_uci_components.py"
    spec = spec_from_file_location("chronus_public_paired_policy", script)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(ValueError):
        module._paired_verified_work(np.ones((2, 2), dtype=np.float64),
                                   PhiTensorCore(), depth=4,
                                   repetitions=repetitions, warmup=warmup)

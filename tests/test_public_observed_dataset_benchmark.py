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

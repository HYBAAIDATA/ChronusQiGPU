"""Import graph, lazy loading, and public-API surface for the ``tensor`` package."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tensor_public_api_is_stable():
    import tensor

    expected = {
        "BackendIdentity",
        "CancellationToken",
        "DEFAULT_MAX_TENSOR_BYTES",
        "Deadline",
        "ExactnessMode",
        "MemoryBudget",
        "ModelIdentity",
        "Precision",
        "ProvenanceRecord",
        "ResidualBounds",
        "RouteDecision",
        "TensorBackendUnavailableError",
        "TensorCancelledError",
        "TensorError",
        "TensorExactnessError",
        "TensorMeasurement",
        "TensorMemoryError",
        "TensorOperationSpec",
        "TensorRequest",
        "TensorResult",
        "TensorShape",
        "TensorTimeoutError",
        "TensorValidationError",
        "TruthClass",
        "default_registry",
        "estimate_bytes",
        "execute",
        "preflight_memory",
        "route",
        "telemetry_record",
        "timed_execute",
    }
    assert expected <= set(tensor.__all__)
    for name in expected:
        assert hasattr(tensor, name)


def test_tensor_package_root_has_typing_marker_and_docs():
    root = ROOT / "tensor"
    assert (root / "__init__.py").is_file()
    assert (root / "py.typed").is_file()
    assert (root / "README.md").is_file()
    assert (root / "CAPABILITY_MANIFEST.md").is_file()
    assert (ROOT / "docs" / "TENSOR_ARCHITECTURE.md").is_file()


def test_chronus_adapter_is_not_imported_merely_by_importing_tensor():
    """Importing ``tensor`` must not eagerly import chronus/pyopencl."""
    code = (
        "import sys, tensor; "
        "assert 'chronus' not in sys.modules, sys.modules.keys(); "
        "assert 'chronus.detect' not in sys.modules"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_default_registry_does_not_construct_backends_eagerly():
    """Registering factories must not instantiate the optional backend."""
    code = (
        "import sys\n"
        "from tensor.router import default_registry\n"
        "registry = default_registry()\n"
        "assert 'chronus.detect' not in sys.modules\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_tensor_backends_package_has_protocol_and_registry():
    from tensor.backends import BackendRegistry, TensorBackend

    assert TensorBackend.__name__ == "TensorBackend"
    registry = BackendRegistry()
    assert registry.names() == ()


def test_kellogg_bridge_loaders_are_lazy_and_named_correctly():
    from tensor import kellogg_bridge

    assert callable(kellogg_bridge.load_kellogg_exact_tensor)
    assert callable(kellogg_bridge.load_kellogg_quantum_tensor)
    assert callable(kellogg_bridge.load_kellogg_tensor_ml)
    assert callable(kellogg_bridge.load_exact_tensor_module)
    assert callable(kellogg_bridge.load_quantum_tensor_module)

    assert kellogg_bridge.load_kellogg_exact_tensor().__name__ == "kellogg.exact_tensor"
    assert kellogg_bridge.load_kellogg_quantum_tensor().__name__ == "kellogg.quantum_tensor"
    assert kellogg_bridge.load_kellogg_tensor_ml().__name__ == "kellogg.tensor_ml"


def test_advisor_reexport_matches_canonical_module():
    from tensor import advisor
    from hyba.hybrid import tensor_advisor

    assert advisor.apply_tensor_advice is tensor_advisor.apply_tensor_advice
    assert advisor.WindowRanker is tensor_advisor.WindowRanker
    assert advisor.TensorAdviceViolation is tensor_advisor.TensorAdviceViolation


def test_capability_manifest_covers_declared_features():
    from tensor.capability import CAPABILITY_MANIFEST, render_markdown

    assert "backend.numpy_reference" in CAPABILITY_MANIFEST
    assert "backend.chronus_adapter" in CAPABILITY_MANIFEST
    assert CAPABILITY_MANIFEST["backend.chronus_adapter"]["status"] == "hardware_evidence_required"
    for feature, row in CAPABILITY_MANIFEST.items():
        assert row["status"] in (
            "implemented_tested",
            "hardware_evidence_required",
            "not_implemented",
        ), feature
    assert "| Feature | Status |" in render_markdown()

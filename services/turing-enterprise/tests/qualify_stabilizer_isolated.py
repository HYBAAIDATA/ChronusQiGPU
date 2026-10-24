"""Isolated real stabilizer source qualification, NOT installed VQC integration.

Loads the actual owner module, without replacing it with a stub, then executes
its unchanged independent dense-reference tests. Unrelated package initializers
and the canonical execution/custody path are deliberately not exercised. Run the
separate non-skipping integration gate for installed-runtime qualification.
"""

import importlib.util
from pathlib import Path
import sys

import pytest


def main():
    root = Path(__file__).resolve().parents[3] / "turing_universal_quantum_computer"
    name = "turing_universal_quantum_computer.stabilizer"
    source = root / "turing_universal_quantum_computer/stabilizer.py"
    spec = importlib.util.spec_from_file_location(name, source)
    if spec is None or spec.loader is None:
        raise RuntimeError("actual stabilizer source unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return pytest.main([str(root / "tests/test_stabilizer_measurement.py"), *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())

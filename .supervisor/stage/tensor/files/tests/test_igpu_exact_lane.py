"""The exact lane of chronus.igpu.tensor: turing.tensor from the hyba-turing distribution.

hyba-chronus must keep working without hyba-turing installed, so the lane is imported on first
access only. These tests check the identity of the lane, that the existing exports are unchanged,
that importing chronus.igpu.tensor does not import TURING, and the error raised without TURING.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MISSING = "the exact tensor lane needs the hyba-turing distribution"


def _last_line(code):
    """Run code in a fresh interpreter that can import chronus and turing; return its last output line."""
    env = dict(os.environ)
    paths = [str(ROOT / "src"), str(ROOT / "packages" / "turing" / "src")]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    completed = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True,
                               timeout=300, check=False)
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip().splitlines()[-1]


def test_exact_lane_is_the_turing_tensor_module():
    import turing.tensor
    from chronus.igpu import tensor as igpu_tensor

    assert igpu_tensor.exact is turing.tensor
    assert igpu_tensor.exact.ExactMPS is turing.tensor.ExactMPS
    register = igpu_tensor.exact.evaluate_circuit(3, [("h", (0,), ()), ("cnot", (0, 2), ())])
    assert register.bond_dimensions() == (2, 2)
    assert register.probability("101") == register.probability("000")


def test_existing_exports_are_unchanged():
    from chronus import tensor as chronus_tensor
    from chronus.igpu import tensor as igpu_tensor
    from chronus.tensor.enhanced_representation import EnhancedTensorRepresentation

    assert igpu_tensor.EnhancedTensorRepresentation is EnhancedTensorRepresentation
    assert "exact" not in igpu_tensor.__all__
    assert sorted(igpu_tensor.__all__) == sorted(set(chronus_tensor.__all__) | {"EnhancedTensorRepresentation"})
    for name in chronus_tensor.__all__:
        assert getattr(igpu_tensor, name) is getattr(chronus_tensor, name)
    with pytest.raises(AttributeError):
        getattr(igpu_tensor, "no_such_export")


def test_importing_the_igpu_tensor_module_does_not_import_turing():
    line = _last_line(
        "import sys\n"
        "import chronus.igpu.tensor\n"
        "from chronus.igpu.tensor import *\n"
        "print(sorted(m for m in sys.modules if m == 'turing' or m.startswith('turing.')))\n"
    )
    assert line == "[]"


def test_missing_turing_raises_a_clear_import_error():
    line = _last_line(
        "import sys\n"
        "sys.modules['turing'] = None\n"
        "import chronus.igpu.tensor as lane\n"
        "try:\n"
        "    lane.exact\n"
        "except ImportError as error:\n"
        "    print(type(error).__name__ + ': ' + str(error))\n"
    )
    assert line.startswith("ImportError: " + MISSING)


def test_a_turing_without_the_exact_layer_is_refused():
    line = _last_line(
        "import sys, types\n"
        "sys.modules['turing'] = types.ModuleType('turing')\n"
        "sys.modules['turing.tensor'] = types.ModuleType('turing.tensor')\n"
        "import chronus.igpu.tensor as lane\n"
        "try:\n"
        "    lane.exact\n"
        "except ImportError as error:\n"
        "    print(type(error).__name__ + ': ' + str(error))\n"
    )
    assert line.startswith("ImportError: " + MISSING) and line.endswith("has no exact tensor layer")

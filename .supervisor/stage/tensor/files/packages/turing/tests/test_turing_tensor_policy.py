"""Mechanical exactness and wording checks for the package turing.tensor and its tests.

Sources are located through the imported package (Path(turing.__file__).parent), so the checks run in
the source tree and against the installed wheel alike. The scope is turing/tensor only; the
floating-point Kronecker products in turing/kronecker.py are outside the exact layer and outside this
scan. The document checks for docs/TENSOR.md live in tests/test_turing_repository_policy.py at the
repository root. Claim tokens are stored as code points so that this file never contains them.
"""

import ast
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if sys.path[:1] != [_SRC]:
    sys.path.insert(0, _SRC)

import turing.tensor  # noqa: E402

PACKAGE_DIR = Path(turing.__file__).resolve().parent / "tensor"
SOURCE_FILES = sorted(PACKAGE_DIR.glob("*.py"))
TEST_FILES = sorted(Path(__file__).resolve().parent.glob("test_turing_tensor_*.py"))
EXPECTED_SOURCES = {"__init__.py", "circuit.py", "dense.py", "field.py", "linalg.py", "mps.py", "train.py"}
EXACT_MATH = {"isqrt", "gcd", "lcm", "comb", "perm", "factorial"}
BANNED_MODULES = {"random", "numpy", "cmath", "decimal", "statistics", "secrets", "chronus", "scipy"}
BANNED_CALLS = {"float", "complex", "round"}
FLOATING_POINT_MODULES = {"state", "operator", "gates", "measurement", "kronecker"}


def _decode(*code_points):
    return tuple("".join(chr(c) for c in word) for word in code_points)


CLAIM_TOKENS = _decode(
    (105, 110, 102, 105, 110, 105, 116, 101),
    (101, 120, 112, 111, 110, 101, 110, 116, 105, 97, 108),
    (117, 110, 108, 105, 109, 105, 116, 101, 100),
    (49, 48, 48, 120),
)
CODE_WORDING = _decode(
    (115, 105, 109, 117, 108, 97, 116),
    (115, 112, 101, 101, 100, 117, 112),
    (98, 114, 101, 97, 107, 116, 104, 114, 111, 117, 103, 104),
    (113, 117, 97, 110, 116, 117, 109, 32, 97, 100, 118, 97, 110, 116, 97, 103, 101),
)


def _violations(source):
    tree = ast.parse(source)
    found = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Constant) and type(node.value).__name__ in ("float", "complex"):
            found.append((line, "non-integer numeric literal"))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BANNED_CALLS:
            found.append((line, f"call to {node.func.id}"))
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "math" \
                and node.attr not in EXACT_MATH:
            found.append((line, f"math.{node.attr}"))
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) \
                and isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant):
            found.append((line, "true division of literals"))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in BANNED_MODULES or root == "math":
                    found.append((line, f"import {alias.name}"))
                if alias.name.split(".")[:2] == ["turing", "kronecker"]:
                    found.append((line, f"import of the floating-point module {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            parts = (node.module or "").split(".")
            root = parts[0]
            if node.level == 0 and root in BANNED_MODULES:
                found.append((line, f"from {node.module} import"))
            if node.level == 0 and root == "math":
                for alias in node.names:
                    if alias.name not in EXACT_MATH:
                        found.append((line, f"from math import {alias.name}"))
            if node.level == 0 and parts[:2] == ["turing", "kronecker"]:
                found.append((line, f"import of the floating-point module {node.module}"))
            if node.level >= 2 and root in FLOATING_POINT_MODULES:
                found.append((line, f"relative import of the floating-point module {root}"))
    return found


def test_the_package_has_the_expected_modules():
    assert {path.name for path in SOURCE_FILES} == EXPECTED_SOURCES
    assert len(TEST_FILES) >= 7


def test_no_floating_point_randomness_numpy_or_chronus_in_the_package():
    problems = []
    for path in SOURCE_FILES:
        found = _violations(path.read_text(encoding="utf-8"))
        problems.extend((path.name, line, message) for line, message in found)
    assert problems == []


def test_the_scanner_detects_violations():
    samples = {
        "x = 0.5": "non-integer numeric literal",
        "x = float(2)": "call to float",
        "import math\nx = math.sqrt(2)": "math.sqrt",
        "from math import sqrt": "from math import sqrt",
        "import numpy": "import numpy",
        "from random import choice": "from random import",
        "import chronus.tensor": "import chronus.tensor",
        "x = 1 / 2": "true division of literals",
        "from ..state import QuantumState": "relative import of the floating-point module state",
        "from ..kronecker import tensor_states": "relative import of the floating-point module kronecker",
        "from turing.kronecker import tensor_states": "import of the floating-point module turing.kronecker",
    }
    for source, expected in samples.items():
        messages = [message for _, message in _violations(source)]
        assert any(expected in message for message in messages), (source, messages)
    assert _violations("from math import gcd, isqrt\nx = Fraction(1, 2)") == []


def test_package_imports_stay_inside_turing():
    for path in SOURCE_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                assert node.module.split(".")[0] in {"__future__", "fractions", "typing", "operator", "math",
                                                     "dataclasses"}, node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] in {"operator"}, alias.name
            elif isinstance(node, ast.ImportFrom) and node.level == 2:
                assert node.module in ("algebra", "algebra.cyclotomic"), node.module


def test_the_floating_point_kronecker_products_stay_outside_the_exact_package():
    package = sys.modules["turing"]
    kronecker = sys.modules["turing.kronecker"]
    assert package.tensor_states is kronecker.tensor_states
    assert package.tensor_operators is kronecker.tensor_operators
    assert Path(kronecker.__file__).resolve().parent == Path(package.__file__).resolve().parent
    assert not hasattr(turing.tensor, "tensor_states") and not hasattr(turing.tensor, "tensor_operators")
    assert not {"tensor_states", "tensor_operators"} & set(turing.tensor.__all__)
    assert not (Path(package.__file__).resolve().parent / "tensor.py").exists()


def test_claim_tokens_and_wording():
    problems = []
    for path in SOURCE_FILES + TEST_FILES:
        text = path.read_text(encoding="utf-8").lower()
        for token in CLAIM_TOKENS + CODE_WORDING:
            if token in text:
                problems.append((path.name, token))
    assert problems == []

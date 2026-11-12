"""Mechanical checks of the exactness and wording rules for the new TURING modules.

Banned words are stored as code points so that this file never contains them.
"""

import ast
import sys
from pathlib import Path

import pytest

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if sys.path[:1] != [_SRC]:
    sys.path.insert(0, _SRC)

PACKAGE = Path(__file__).resolve().parents[1]
if not (PACKAGE / "src" / "turing").is_dir():
    pytest.skip("source-policy checks require a source checkout", allow_module_level=True)

SOURCE_FILES = sorted((PACKAGE / "src" / "turing" / "algebra").glob("*.py")) + \
    sorted((PACKAGE / "src" / "turing" / "algorithms").glob("*.py"))
TEST_FILES = sorted((PACKAGE / "tests").glob("test_turing_*.py"))
DOCUMENT = PACKAGE / "docs" / "algorithms.md"


def _decode(*code_points):
    return tuple("".join(chr(c) for c in word) for word in code_points)


CLAIM_TOKENS = _decode(
    (105, 110, 102, 105, 110, 105, 116, 101),
    (101, 120, 112, 111, 110, 101, 110, 116, 105, 97, 108),
    (117, 110, 108, 105, 109, 105, 116, 101, 100),
    (49, 48, 48, 120),
)
WORDING = _decode(
    (115, 105, 109, 117, 108, 97, 116),
    (112, 104, 121, 115, 105, 99, 97, 108, 32, 113, 117, 98, 105, 116),
    (102, 97, 117, 108, 116, 45, 116, 111, 108, 101, 114, 97, 110, 116),
    (102, 97, 117, 108, 116, 32, 116, 111, 108, 101, 114, 97, 110, 116),
    (102, 97, 117, 108, 116, 32, 116, 111, 108, 101, 114, 97, 110, 99, 101),
    (113, 117, 97, 110, 116, 117, 109, 32, 97, 100, 118, 97, 110, 116, 97, 103, 101),
    (115, 112, 101, 101, 100, 117, 112),
    (115, 112, 101, 101, 100, 45, 117, 112),
    (98, 114, 101, 97, 107, 116, 104, 114, 111, 117, 103, 104),
)
BANNED_CALLS = {"float", "complex", "round"}
BANNED_MODULES = {"random", "numpy", "cmath", "decimal", "statistics", "secrets", "chronus"}
EXACT_MATH = {"isqrt", "gcd", "lcm", "comb", "perm", "factorial"}
LEGACY_MODULES = {"state", "operator", "gates", "measurement", "tensor"}
NEW_SUBPACKAGES = {"algebra", "algorithms"}


def _violations(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Constant) and type(node.value).__name__ in ("float", "complex"):
            found.append((line, "non-integer numeric literal"))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BANNED_CALLS:
            found.append((line, f"call to {node.func.id}"))
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "math":
            found.append((line, "math module attribute"))
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) \
                and isinstance(node.left, ast.Constant) and isinstance(node.right, ast.Constant):
            found.append((line, "true division of literals"))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "math" or parts[0] in BANNED_MODULES:
                    found.append((line, f"import {alias.name}"))
                if parts[0] == "turing" and (len(parts) == 1 or parts[1] not in NEW_SUBPACKAGES):
                    found.append((line, f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            parts = module.split(".") if module else []
            if node.level == 0 and parts:
                if parts[0] in BANNED_MODULES:
                    found.append((line, f"from {module} import"))
                if parts[0] == "math" and any(alias.name not in EXACT_MATH for alias in node.names):
                    found.append((line, "non-exact math import"))
                if parts[0] == "turing" and (len(parts) == 1 or parts[1] not in NEW_SUBPACKAGES):
                    found.append((line, f"from {module} import"))
            if node.level >= 2:
                targets = parts[:1] if parts else [alias.name for alias in node.names]
                if any(target in LEGACY_MODULES for target in targets):
                    found.append((line, "relative import of a floating-point module"))
    return found


def test_new_files_are_present():
    names = {path.name for path in SOURCE_FILES}
    for expected in ("cyclotomic.py", "reduction.py", "oracles.py", "walsh.py", "deutsch_jozsa.py",
                     "bernstein_vazirani.py", "simon.py", "grover.py", "qft.py", "qpe.py", "shor.py",
                     "clifford.py", "structured.py"):
        assert expected in names
    assert len(TEST_FILES) >= 10
    assert DOCUMENT.is_file()


def test_no_floating_point_randomness_or_legacy_imports():
    problems = []
    for path in SOURCE_FILES + TEST_FILES:
        problems.extend((path.name, line, message) for line, message in _violations(path))
    assert problems == []


def test_wording_and_claim_tokens():
    problems = []
    for path in SOURCE_FILES + TEST_FILES + [DOCUMENT]:
        text = path.read_text(encoding="utf-8").lower()
        for token in CLAIM_TOKENS + WORDING:
            if token in text:
                problems.append((path.name, token))
    assert problems == []


def test_new_modules_do_not_load_floating_point_modules():
    tree_imports = set()
    for path in SOURCE_FILES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.level >= 1 and node.module:
                tree_imports.add(node.module.split(".")[0])
    assert tree_imports.isdisjoint(LEGACY_MODULES)

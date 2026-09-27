#!/usr/bin/env python3
"""Reject runtime floating-point constructs in the exact MLA1517 math core."""

from __future__ import annotations
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ROOT / "python/mla1517/core.py",
    ROOT / "python/mla1517/rings.py",
    ROOT / "python/mla1517/quantum.py",
    ROOT / "python/mla1517/accelerator.py",
]
violations = []
for path in FILES:
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            violations.append(f"{path}:{node.lineno}:float literal")
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in {"float", "sqrt"}:
                violations.append(f"{path}:{node.lineno}:{fn.id} call")
            if isinstance(fn, ast.Attribute) and fn.attr in {"sqrt", "isclose"}:
                violations.append(f"{path}:{node.lineno}:math.{fn.attr} call")
if violations:
    print("\n".join(violations))
    raise SystemExit(1)
kernel = (ROOT / "kernels/exact_quantum_kernel.cl").read_text()
kernel_code = re.sub(r"/\*.*?\*/|//[^\n]*", "", kernel, flags=re.S)
if re.search(r"\b(float|double)\b", kernel_code):
    raise SystemExit("kernels/exact_quantum_kernel.cl contains floating-point types")
print('{"status":"PASS","files":4,"kernels":1,"no_float_runtime":true}')

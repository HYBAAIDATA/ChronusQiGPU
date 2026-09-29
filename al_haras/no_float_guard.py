"""Static guard for accidental floating-point use in declared exact paths."""

from __future__ import annotations

import ast
import re
from pathlib import Path


class FloatForbidden(ValueError):
    pass


_FLOAT_NAMES = {"float", "double", "float16", "float32", "float64", "double_t"}


def scan_python(path: Path) -> None:
    tree = ast.parse(path.read_text(), filename=str(path))
    parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            raise FloatForbidden(f"{path}:{node.lineno}: float literal")
        if isinstance(node, ast.Name) and node.id.casefold() in _FLOAT_NAMES:
            parent = parents.get(node)
            # Exact APIs may explicitly reject floating input. Merely naming
            # the runtime type as isinstance(..., float) performs no floating
            # arithmetic and must not force callers to silently accept it.
            rejection_guard = (
                isinstance(parent, ast.Call)
                and isinstance(parent.func, ast.Name)
                and parent.func.id == "isinstance"
                and node in parent.args[1:]
            )
            if not rejection_guard:
                raise FloatForbidden(f"{path}:{node.lineno}: float type/cast")
        if isinstance(node, ast.Attribute) and node.attr.casefold() in _FLOAT_NAMES:
            raise FloatForbidden(f"{path}:{node.lineno}: float attribute")


def scan_native(path: Path) -> None:
    text = re.sub(r"//.*?$|/\*.*?\*/", "", path.read_text(), flags=re.M | re.S)
    match = re.search(
        r"\b(float|double|half|float16|float32|float64)\b|(?<![\w.])\d+\.\d+(?:[eE][+-]?\d+)?[fFlL]?",
        text,
    )
    if match:
        raise FloatForbidden(f"{path}: forbidden token {match.group(0)}")


def scan_paths(paths: list[Path]) -> tuple[str, ...]:
    scanned = []
    for path in paths:
        if not path.is_file():
            continue
        (scan_python if path.suffix == ".py" else scan_native)(path)
        scanned.append(str(path))
    return tuple(scanned)

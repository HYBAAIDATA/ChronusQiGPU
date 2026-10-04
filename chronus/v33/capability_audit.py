"""Machine-check the complete Chronos v3.3 mathematical capability surface."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from importlib import resources
import inspect
import json
from typing import Any


@dataclass(frozen=True)
class CapabilityAuditReport:
    modules: int
    classes: int
    functions: int
    missing: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.missing


def load_capability_manifest() -> list[dict[str, Any]]:
    """Load the inventory from package data, including installed wheels."""

    text = resources.files("chronus.v33").joinpath("CAPABILITY_MANIFEST.json").read_text(
        encoding="utf-8"
    )
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("Chronos capability manifest must be a list")
    return data


def _module_name(relative_file: str) -> str:
    path = relative_file.removesuffix(".py").replace("/", ".")
    if path == "__init__":
        return "chronus.v33"
    if path.endswith(".__init__"):
        path = path[: -len(".__init__")]
    return f"chronus.v33.{path}"


def audit_capability_surface(*, raise_on_missing: bool = True) -> CapabilityAuditReport:
    """Import and verify every module, class, and function in the inventory."""

    manifest = load_capability_manifest()
    missing: list[str] = []
    class_count = 0
    function_count = 0

    for entry in manifest:
        module_name = _module_name(str(entry["file"]))
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            missing.append(f"{module_name}: import failed: {type(exc).__name__}: {exc}")
            continue

        for name in entry.get("classes", []):
            class_count += 1
            value = getattr(module, name, None)
            if not inspect.isclass(value):
                missing.append(f"{module_name}.{name}: class missing")

        for name in entry.get("functions", []):
            function_count += 1
            value = getattr(module, name, None)
            if not callable(value) or inspect.isclass(value):
                missing.append(f"{module_name}.{name}: function missing")

    report = CapabilityAuditReport(
        modules=len(manifest),
        classes=class_count,
        functions=function_count,
        missing=tuple(missing),
    )
    if raise_on_missing and not report.ok:
        raise RuntimeError("Chronos capability surface is incomplete:\n" + "\n".join(report.missing))
    return report


__all__ = ["CapabilityAuditReport", "audit_capability_surface", "load_capability_manifest"]

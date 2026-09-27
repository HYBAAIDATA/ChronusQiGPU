"""OpenCL emitter — lowers a KernelSpec onto canonical kernel sources.

Byte-compatibility is by construction: the emitted source IS the canonical
.cl file's bytes and the entry name is asserted present as
``__kernel void <entry>``. Specs without a canonical kernel raise
``NoCanonicalKernel`` — they bind the exact CPU oracle instead of a
generated kernel that could silently diverge.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hyba.math_ir.specs import get_spec

_REPO_ROOT = Path(__file__).resolve().parents[2]


class NoCanonicalKernel(KeyError):
    """Raised when a spec has no canonical .cl source to emit."""


@dataclass(frozen=True)
class EmittedKernel:
    source: str
    entry: str
    source_path: str


def emit_opencl(spec_name: str) -> EmittedKernel:
    """Return the canonical OpenCL source + entry name for ``spec_name``.

    Raises ``NoCanonicalKernel`` for ops defined only by their CPU oracle —
    no kernel is generated where none exists in the tree.
    """
    spec = get_spec(spec_name)
    if spec.canonical_source is None or not spec.entry:
        raise NoCanonicalKernel(
            f"{spec.name}: no canonical OpenCL source — CPU oracle is authoritative"
        )
    path = _REPO_ROOT / spec.canonical_source
    if not path.is_file():
        raise FileNotFoundError(f"canonical kernel source missing: {path}")
    source = path.read_text(encoding="utf-8")
    if f"__kernel void {spec.entry}" not in source:
        raise ValueError(
            f"entry {spec.entry!r} not present in canonical source {spec.canonical_source}"
        )
    return EmittedKernel(source=source, entry=spec.entry, source_path=str(path))


__all__ = ["EmittedKernel", "NoCanonicalKernel", "emit_opencl"]

#!/usr/bin/env python3
"""One-shot repository migration: canonicalise the iGPU offering as Chronus.

Turing remains the compute substrate. Chronus owns the device/runtime/offering
surface. This script intentionally creates no compatibility package or aliases.
It is executed once on feat/chronos-recovery and removed by its workflow after
validation.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    "legacy",  # historical evidence stays historical; it is not an active shim.
}
TEXT_SUFFIXES = {
    ".py", ".md", ".toml", ".yml", ".yaml", ".json", ".ts", ".tsx",
    ".js", ".jsx", ".cl", ".txt", ".sh", ".cfg", ".ini", ".html",
    ".css", ".xml", ".csv", ".env", ".example",
}


def active(path: Path) -> bool:
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        return False
    return not any(part in SKIP_DIRS for part in rel.parts)


def move(src: str, dst: str) -> None:
    source = ROOT / src
    target = ROOT / dst
    if not source.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    source.rename(target)


def rename_matching_names() -> None:
    # Bottom-up so children are renamed before their parents.
    candidates = [p for p in ROOT.rglob("*") if active(p) and "igpu" in p.name]
    for path in sorted(candidates, key=lambda p: len(p.parts), reverse=True):
        if not path.exists():
            continue
        target = path.with_name(path.name.replace("igpu", "chronus"))
        if target.exists():
            raise RuntimeError(f"rename collision: {path} -> {target}")
        path.rename(target)


# The feature branch staged a byte-identical copy first so the migration could
# be prepared without breaking the old namespace. Replace that staging copy with
# the actual canonical move now.
chronus = ROOT / "chronus"
igpu = ROOT / "igpu"
if igpu.exists():
    if chronus.exists():
        shutil.rmtree(chronus)
    igpu.rename(chronus)

# Product-facing surfaces outside the old package join Chronus as well.
move("hyba/virtual_gpu.py", "chronus/fabric.py")
move("hyba/gpureport.py", "chronus/report.py")
move("docs/SUPER_GPU_SUBSTRATE.md", "docs/CHRONUS_SUBSTRATE.md")
move("docs/GPU_FLEET.md", "docs/CHRONUS_FLEET.md")
move("scripts/benchmark_super_gpu.py", "scripts/benchmark_chronus.py")
move("reports/super_gpu_benchmark.json", "reports/chronus_benchmark.json")
move("tests/test_super_gpu.py", "tests/test_chronus_fabric.py")
move("gpu-aethel-review.md", "chronus-aethel-review.md")

# Rename every remaining active path that exposes the old product namespace:
# scripts, tests, telemetry modules, deployment overlays, spec files, reports.
rename_matching_names()

REPLACEMENTS = [
    # Most-specific symbols first.
    ("IGPUOpenCLUnavailable", "ChronusOpenCLUnavailable"),
    ("IGPUOpenCLEngine", "ChronusOpenCLEngine"),
    ("ResidentIGPUEnsemble", "ResidentChronusEnsemble"),
    ("ResidentIGPUState", "ResidentChronusState"),
    ("IgpuTelemetry", "ChronusTelemetry"),
    ("IGpuSku", "ChronusSku"),
    ("TensorCoreGPU_Context", "ChronusContext"),
    ("IGPU_SCALE_RUNGS", "CHRONUS_SCALE_RUNGS"),
    ("IGPU_", "CHRONUS_"),
    ("SuperGPU", "ChronusFabric"),
    ("super_gpu", "chronus_fabric"),
    ("SUPER_GPU", "CHRONUS_FABRIC"),
    ("hyba.virtual_gpu", "chronus.fabric"),
    ("hyba.gpureport", "chronus.report"),
    # Namespace/product identity. Generic technical 'GPU' and 'iGPU' words are
    # intentionally not blanket-replaced: OpenCL/CUDA/Metal and integrated-GPU
    # hardware remain factual backend descriptions.
    ("igpu", "chronus"),
    ("IGPU", "Chronus"),
]

PRODUCT_LANGUAGE = [
    ("the consolidated iGPU package", "the Chronus package"),
    ("consolidated iGPU package", "Chronus package"),
    ("consolidated iGPU device object", "canonical Chronus device object"),
    ("One handle over the consolidated iGPU substrate", "One handle over the Chronus offering"),
    ("Resident iGPU OpenCL engine", "Chronus resident OpenCL engine"),
    ("iGPU package", "Chronus package"),
    ("iGPU substrate", "Chronus substrate"),
    ("iGPU device object", "Chronus device object"),
]


def should_edit(path: Path) -> bool:
    if not path.is_file() or not active(path):
        return False
    if path.name in {"LICENSE"}:
        return False
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in {
        "Dockerfile", "Makefile", ".env.example", ".dockerignore",
    }


for path in list(ROOT.rglob("*")):
    if not should_edit(path):
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    original = text
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    for old, new in PRODUCT_LANGUAGE:
        text = text.replace(old, new)
    # Detection asks whether hardware is integrated, not whether it is the
    # Chronus product. Preserve that semantic after the namespace replacement.
    text = text.replace("is_chronus", "is_integrated")
    text = text.replace("known_chronus", "known_integrated")
    if text != original:
        path.write_text(text, encoding="utf-8")

# Packaging: Chronus is a real package, not a source-tree accident.
pyproject = ROOT / "pyproject.toml"
if pyproject.exists():
    text = pyproject.read_text(encoding="utf-8")
    if '"chronus" = "chronus"' not in text:
        text = text.replace(
            'package-dir = {"" = "mla1517_platform_v3.4/python",',
            'package-dir = {"" = "mla1517_platform_v3.4/python", "chronus" = "chronus",',
        )
    if 'packages = ["chronus", "chronus.seam",' not in text:
        text = text.replace('packages = ["lucas",', 'packages = ["chronus", "chronus.seam", "lucas",')
    if 'chronus = ["spec/*.json", "kernels/*.cl"]' not in text:
        text = text.replace(
            '[tool.setuptools.package-data]\n',
            '[tool.setuptools.package-data]\nchronus = ["spec/*.json", "kernels/*.cl"]\n',
        )
    pyproject.write_text(text, encoding="utf-8")

# Canonical public surface. There is intentionally no `igpu` alias or sys.modules
# compatibility entry anywhere in the new package.
init_py = ROOT / "chronus" / "__init__.py"
init_py.write_text(
    '''"""Chronus — HYBA's canonical iGPU offering.\n\nTuring is the computation substrate; Chronus is the device/runtime offering\nthat binds measured hardware, resident execution, topology, telemetry, fleet\nrouting and attestation to that compute substrate.\n"""\n\nfrom .device import CLAIM_BOUNDARY, Chronus\nfrom .engine import (\n    ChronusOpenCLEngine,\n    ChronusOpenCLUnavailable,\n    ResidentChronusEnsemble,\n    ResidentChronusState,\n)\nfrom .fabric import ChronusFabric\nfrom .telemetry import ChronusTelemetry, get_telemetry\n\n__all__ = [\n    "Chronus",\n    "ChronusFabric",\n    "ChronusOpenCLEngine",\n    "ChronusOpenCLUnavailable",\n    "ChronusTelemetry",\n    "ResidentChronusEnsemble",\n    "ResidentChronusState",\n    "CLAIM_BOUNDARY",\n    "get_telemetry",\n]\n''',
    encoding="utf-8",
)

readme = ROOT / "chronus" / "README.md"
readme.write_text(
    '''# Chronus\n\n**Chronus is the canonical HYBA iGPU offering. Turing is compute.**\n\nChronus owns the hardware-facing product boundary: device census and selection,\nresident OpenCL execution, mathematical-state memory, the punch host, kernels,\nM32/H4 topology bindings, measured telemetry, multi-device/fleet routing, and\ndispatch attestation. Turing remains the mathematical computation substrate\nChronus invokes; this package does not rename or absorb Turing.\n\n## Canonical pipeline\n\n`Turing compute -> Chronus route/device -> backend dispatch -> attestation -> measured telemetry`\n\nBackends such as OpenCL, CUDA, Metal and CPU reference paths retain their real\ntechnical names. `GPU`/`integrated GPU` remains a hardware description; it is\nnot a competing product namespace.\n\n## Truth boundary\n\nChronus reports what ran. Measured dispatches are measured; projections remain\nlabelled projections; unavailable hardware is unavailable. For mining,\nSHA-256d target verification remains the sole acceptance authority. Historical\nChronos-era performance targets (including fixed 8K frame-time, perfect-GI,\ninfinite-resolution and fixed PULVINI compression ratios) are not promoted here\nas measured Chronus capabilities without reproducible evidence.\n\n## No compatibility shim\n\nThe previous active `igpu` namespace is removed by the Chronus migration. New\ncode imports `chronus`; no alias package or `sys.modules` redirection is kept.\n''',
    encoding="utf-8",
)

docs = ROOT / "docs" / "CHRONUS.md"
docs.write_text(
    '''# Chronus architecture\n\nChronus is HYBA's iGPU offering. Turing is the compute engine/substrate.\n\n- **Turing:** mathematical computation and algorithmic execution.\n- **Chronus:** hardware-facing iGPU product/runtime, device routing, resident\n  execution, memory, kernels, telemetry, fleet composition and attestation.\n- **Backends:** OpenCL/CUDA/Metal/CPU are execution substrates selected and\n  reported by Chronus; they are not product identities.\n\nChronus consolidates the former active iGPU package and the Super-GPU product\nsurface. It is a real namespace migration, not an alias. Historical material\nunder `legacy/` is retained as provenance only and is not importable through a\ncompatibility surface.\n''',
    encoding="utf-8",
)

# Migration guard: active code must never regress to the retired namespace.
namespace_test = ROOT / "tests" / "test_chronus_namespace.py"
namespace_test.write_text(
    '''from __future__ import annotations\n\nfrom pathlib import Path\n\nimport chronus\nfrom chronus import Chronus, ChronusFabric, ChronusOpenCLEngine, ChronusTelemetry\n\nROOT = Path(__file__).resolve().parents[1]\nSKIP = {"legacy", ".git", "node_modules", ".venv", "venv", "dist", "build"}\nTEXT_SUFFIXES = {".py", ".md", ".toml", ".yml", ".yaml", ".json", ".ts", ".tsx", ".js", ".cl"}\n\n\ndef _active(path: Path) -> bool:\n    rel = path.relative_to(ROOT)\n    return not any(part in SKIP for part in rel.parts)\n\n\ndef test_chronus_is_real_public_namespace():\n    assert Chronus.__module__ == "chronus.device"\n    assert ChronusFabric.__module__ == "chronus.fabric"\n    assert ChronusOpenCLEngine.__module__ == "chronus.engine"\n    assert ChronusTelemetry.__module__ == "chronus.telemetry"\n    assert chronus.__name__ == "chronus"\n\n\ndef test_no_active_igpu_namespace_or_compatibility_shim():\n    assert not (ROOT / "igpu").exists()\n    offenders = []\n    forbidden = ("from igpu", "import igpu", "igpu.", "igpu/", "IGPUOpenCL", "IgpuTelemetry", "ResidentIGPU", "IGpuSku")\n    for path in ROOT.rglob("*"):\n        if not path.is_file() or not _active(path) or path.suffix.lower() not in TEXT_SUFFIXES:\n            continue\n        text = path.read_text(encoding="utf-8", errors="ignore")\n        if any(token in text for token in forbidden):\n            offenders.append(str(path.relative_to(ROOT)))\n    assert offenders == []\n\n\ndef test_turing_remains_separate_compute_substrate():\n    import turing_core\n    assert turing_core is not chronus\n''',
    encoding="utf-8",
)

# Final static sanity checks before the workflow runs Python/pytest.
if (ROOT / "igpu").exists():
    raise RuntimeError("retired igpu package still exists")
if not (ROOT / "chronus" / "device.py").exists():
    raise RuntimeError("Chronus device implementation missing")

print("Chronus migration applied: Turing remains compute; Chronus owns the iGPU offering.")

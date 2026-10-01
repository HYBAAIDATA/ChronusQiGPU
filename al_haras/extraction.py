"""Non-destructive fork routing and public-API contracts."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import PurePosixPath

ROUTES = (
    ("chronus/mla1517/mining/geometry.py", "CORE_AS_M32"),
    ("chronus/mla1517/*.py", "CORE"),
    ("chronus/mla1517_platform/host/*", "CORE"),
    ("chronus/mla1517_platform/kernels/*", "CORE"),
    ("chronus/mla1517_platform/rtl/*", "CORE_REFERENCE_IP"),
    ("hyba/*", "CORE_RENAMED_HYBA_DEVICES"),
    ("mining/*", "PYTHIA"),
    ("frontend/*", "PYTHIA"),
    ("toe/unified/*", "ENTERPRISE"),
    ("al_haras/*", "ENTERPRISE"),
    ("l_hras/*", "ENTERPRISE"),
    ("kellogg/*", "ENTERPRISE"),
    ("deploy/azure/*", "ENTERPRISE"),
    ("legacy/*", "DROP"),
    ("Intelligence/*", "LEGACY_OR_OWNED"),
    ("agi/*", "LEGACY_OR_OWNED"),
    ("asi/*", "LEGACY_OR_OWNED"),
    ("millennium/*", "LEGACY_OR_OWNED"),
    ("chronus/*", "LEGACY_OR_OWNED"),
    ("pci/*", "LEGACY_OR_OWNED"),
    ("pythagoras/*", "LEGACY_OR_OWNED"),
    ("omega/*", "LEGACY_OR_OWNED"),
    ("mtheory/*", "LEGACY_OR_OWNED"),
    ("manifold_pool_coordinator.py", "PYTHIA"),
    ("headless_miner.py", "PYTHIA"),
    ("control_api.py", "PYTHIA"),
    ("salamander_*.py", "PYTHIA"),
    ("agentic_mining.py", "PYTHIA"),
    ("intelligence_*.py", "PYTHIA"),
    ("toe_*.py", "PYTHIA"),
    ("docker-compose*.yml", "PYTHIA"),
)


def route_path(path: str) -> str:
    normalized = str(PurePosixPath(path))
    for pattern, destination in ROUTES:
        if fnmatch(normalized, pattern):
            return destination
    raise ValueError(f"unrouted path: {path}")


@dataclass(frozen=True)
class ExtractionStage:
    id: int
    name: str
    destructive: bool
    prerequisites: tuple[str, ...]
    outputs: tuple[str, ...]


STAGES = (
    ExtractionStage(
        0,
        "PYTHIA hygiene",
        True,
        ("clean working tree", "baseline tests"),
        ("classified legacy", "math_folding canonicalized"),
    ),
    ExtractionStage(
        1,
        "extract mla1517-core",
        True,
        ("stage0 approved", "target repository exists", "history preservation approved"),
        ("versioned core package", "carried gates"),
    ),
    ExtractionStage(
        2, "wire PYTHIA", True, ("core 0.1.0 published",), ("public imports only", "import audit")
    ),
    ExtractionStage(
        3,
        "seed Enterprise",
        True,
        ("core 0.1.0 published", "prototype ownership approved"),
        ("schema v2", "enterprise facade"),
    ),
)

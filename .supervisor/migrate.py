#!/usr/bin/env python3
"""Supervisor consolidation, 11 Nov 2026: TURING and packaging scope only.

Non-destructive: every move uses `git mv` so history follows the file, and
nothing is deleted. Out of scope on purpose (owned by other workstreams or
carrying their instructions): the BLOCKER patches, the qigpu_* acceleration
forks, the root AL HARAS and mining scripts, chronus_source_backup/ and every
workflow file. The script stops at the first unexpected state.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
DATE = "2026-11-11"


def run(*cmd: str) -> str:
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"FAILED: {' '.join(cmd)}\n{result.stdout}\n{result.stderr}")
    return result.stdout


def mv(src: str, dst: str) -> bool:
    if not (ROOT / src).exists():
        print(f"absent, skipped: {src}")
        return False
    (ROOT / dst).parent.mkdir(parents=True, exist_ok=True)
    run("git", "mv", src, dst)
    print(f"moved: {src} -> {dst}")
    return True


def read(path: str) -> str:
    return (ROOT / path).read_bytes().decode("utf-8")


def write(path: str, text: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(text.encode("utf-8"))
    run("git", "add", path)
    print(f"wrote: {path}")


def edit(path: str, old: str, new: str, count: int = 1) -> None:
    raw = read(path)
    if "\r\n" in raw:
        old, new = old.replace("\n", "\r\n"), new.replace("\n", "\r\n")
    found = raw.count(old)
    if found != count:
        sys.exit(f"FAILED edit {path}: expected {count} occurrence(s), found {found}: {old[:90]!r}")
    (ROOT / path).write_bytes(raw.replace(old, new).encode("utf-8"))
    run("git", "add", path)
    print(f"edited: {path}")


def append(path: str, text: str) -> None:
    raw = read(path)
    newline = "\r\n" if "\r\n" in raw else "\n"
    if raw and not raw.endswith("\n"):
        raw += newline
    (ROOT / path).write_bytes((raw + text.replace("\n", newline)).encode("utf-8"))
    run("git", "add", path)
    print(f"appended: {path}")


IMPORT_TURING = re.compile(r"^([ \t]*)(from|import)([ \t]+)turing(?=[ \t.])", re.M)


def rewrite_turing_imports(path: Path) -> int:
    raw = path.read_bytes().decode("utf-8")
    new, count = IMPORT_TURING.subn(lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}turing.exact", raw)
    if count:
        path.write_bytes(new.encode("utf-8"))
        run("git", "add", str(path.relative_to(ROOT)))
        print(f"turing imports -> turing.exact ({count}): {path.relative_to(ROOT)}")
    return count


DIAG_README = """# Root diagnostic outputs archived on 2026-11-11

These files were tool outputs and small local helpers committed at the repository
root between 7 and 11 November 2026. They are kept unchanged for traceability and
are not inputs to any build, test or CI job. They were moved here, not edited or
deleted, so that the repository root carries only project files.

| File | What it is |
|---|---|
| cov_output.txt | coverage report text from a local run |
| test_output.txt, test_result.txt | local test-run summaries |
| tree_output.txt, filelist.txt | directory listings of a local working copy |
| pulvini_output.txt, edge_output.txt | console output captured from local runs |
| build_ci_failed.log | log of a failed local build |
| .coveragemp | coverage data file |
| full_documentation.txt, paradigm_shift.txt | short text notes |
| ARTIFACT_SUMMARY.md | summary note written for an earlier merge |
| read_cov.py, src_turing_read_cov.py | helpers that print part of the coverage text |
| src_turing__rest.txt | empty placeholder previously inside src/turing |

Use `git log --follow <path>` to see each file's history.
"""

TURING_SOURCES_README = """# TURING source snapshots archived on 2026-11-11

* `exact_primitive_library-v3.py` is the single-file exact cyclotomic library from
  which the TURING exact layer was built. Its file name contains a hyphen, so it
  could not be imported as a module. The maintained implementation is
  `turing.exact` (packages/turing/src/turing/exact), tested by tests/test_turing.py.
* `qudit_qec.py` is a demonstration script for the exact qudit stabilizer tableau.
  It imports a module named `exact_primitive_library_v3`, which does not exist in
  this repository, so it did not run as committed. The tableau it exercises is
  `turing.exact.StabilizerTableauZetaP`.

Both files are unchanged. Use `git log --follow <path>` for their history.
"""

ENTRYPOINTS_README = """# Root API entry points archived on 2026-11-11

`production_hr_api.py` and `production_hr_api-v2.py` were thin wrappers that put
src/ on sys.path and re-exported the FastAPI applications and tensor classes.
The maintained modules are `chronus.service.production_hr_api` and
`chronus.service.production_hr_api_v2`. tests/test_enhanced_tensor_representation_v2.py
now imports the application from `chronus.service.production_hr_api_v2` directly;
its test cases are unchanged. Both files here are unchanged.
"""

TURING_README_APPEND = """
## Exact cyclotomic layer: `turing.exact`

Since 11 November 2026 this distribution also carries the exact cyclotomic
library that previously lived at `src/turing` as a second top-level package
named `turing` (the two collided on import). It is now `turing.exact`
(rings Z[zeta_p] and Q(zeta_p), exact states, unitaries, measurement,
entanglement measures and the qudit stabilizer tableau). Its tests are
tests/test_turing.py at the repository root.

TURING is the foundation layer: it never imports `chronus`. Chronus depends on
TURING, never the reverse. The distribution is internal (classifier
"Private :: Do Not Upload") and is not delivered to external participants.
"""

TAXONOMY_APPEND = """
## Update 2026-11-11: one TURING distribution

The exact cyclotomic library formerly at `src/turing` (a second top-level
package also named `turing`, which collided with `packages/turing`) now lives
inside the TURING distribution as `turing.exact`
(packages/turing/src/turing/exact). Its tests (tests/test_turing.py) are
unchanged apart from the import path. TURING remains the foundation layer and
does not import `chronus`; Chronus depends on TURING, never the reverse.
"""

TURING_PYPROJECT = """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "hyba-turing"
version = "0.2.0.dev0"
description = "TURING: first-principles finite-dimensional quantum mathematics for HYBA Data, with an exact cyclotomic layer (internal)"
readme = "README.md"
requires-python = ">=3.10"
classifiers = [
  "Private :: Do Not Upload",
  "Development Status :: 3 - Alpha",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.10",
  "Programming Language :: Python :: 3.11",
  "Programming Language :: Python :: 3.12",
  "Programming Language :: Python :: 3.13",
  "Topic :: Scientific/Engineering :: Mathematics",
]

[project.optional-dependencies]
test = ["pytest>=8"]

[tool.setuptools.packages.find]
where = ["src"]
include = ["turing*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
"""

ROOT_PYPROJECT = """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "hyba-chronus"
version = "37.0.0.dev0"
description = "Chronus: the HYBA Data exact-computation platform, bundled with the TURING library (internal distribution)"
readme = "README.md"
requires-python = ">=3.10"
classifiers = [
    "Private :: Do Not Upload",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Operating System :: OS Independent",
    "Intended Audience :: Science/Research",
    "Topic :: Scientific/Engineering :: Mathematics",
]
dependencies = [
    "cryptography>=47.0",
    "fastapi>=0.162.2,<0.163",
    "starlette>=1.3.1,<2",
    "httpx>=0.28,<1",
    "pydantic>=2.9,<3",
    "uvicorn[standard]>=0.27",
    "PyJWT[crypto]>=2.8,<3",
    "opentelemetry-api>=1.25,<2",
    "opentelemetry-sdk>=1.25,<2",
    "SQLAlchemy>=2.0,<3",
    "greenlet>=3.0.0",
    "numpy>=1.26,<3",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "hypothesis>=6.100",
    "numpy>=1.26,<3",
    "joblib>=1.3",
    "pandas>=2.0",
    "scikit-learn>=1.3",
    "statsmodels>=0.14",
]
ml = [
    "joblib>=1.3",
    "pandas>=2.0",
    "scikit-learn>=1.3",
    "statsmodels>=0.14",
]
postgres = [
    "asyncpg>=0.29",
    "alembic>=1.13",
]
accelerator = [
    "numpy>=1.26,<3",
    "pyopencl>=2024.1",
]

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src", "packages/turing/src"]
include = ["chronus*", "turing*"]

[tool.setuptools.package-data]
"chronus.kernels" = ["*.cl"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src", "packages/turing/src"]
addopts = "--basetemp=.pytest_temp"
"""

HERMES_INIT = '''"""Hermes: the Chronus acceleration namespace.

chronus.hermes is the canonical import path for the bounded acceleration
modules. Their implementation currently lives in chronus.acceleration; the
module objects exported here are the same objects:

* chronus.hermes.fourier: bounded discrete Fourier transform of an explicit
  power-of-two vector.
* chronus.hermes.state: bounded state normalisation and unitary application.

Each module's docstring states its numerical contract and tolerance. Exact,
zero-rounding Fourier and phase-estimation routines belong to TURING
(turing.algorithms); Hermes does not re-implement exact cyclotomic arithmetic.
"""

import sys

from chronus.acceleration import fourier, state

sys.modules[__name__ + ".fourier"] = fourier
sys.modules[__name__ + ".state"] = state

__all__ = ["fourier", "state"]
'''

OVID_INIT = '''"""OVID: content-addressed objects, zero-copy pointers and receipts.

First-class import path for the OVID primitives implemented in
chronus.security.ovid; the objects below are the same objects. State is
process-local: OVID is not a durable or distributed store.
"""

from chronus.security.ovid import (
    POINTER_PREFIX,
    OVIDReceipt,
    OVIDStorage,
    OVIDZeroCopyPointer,
    VerifyEndpoint,
)

__all__ = [
    "POINTER_PREFIX",
    "OVIDReceipt",
    "OVIDStorage",
    "OVIDZeroCopyPointer",
    "VerifyEndpoint",
]
'''

THESEUS_INIT = '''"""Theseus: content-addressed reconstruction over OVID.

First-class import path for chronus.storage.theseus: payloads are stored as
OVID objects, assigned a phyllotaxis coordinate and reconstructed with digest
verification. State is process-local; it is not durable across restart.
"""

from chronus.storage.phyllotaxis import PhyllotaxisCoordinate, phyllotaxis_coordinate
from chronus.storage.theseus import (
    StorageIntegrityError,
    TenantStateJournalEntry,
    TenantStorageFabricRegistry,
    TheseusRecord,
    TheseusService,
    tenant_storage_registry,
)

__all__ = [
    "PhyllotaxisCoordinate",
    "StorageIntegrityError",
    "TenantStateJournalEntry",
    "TenantStorageFabricRegistry",
    "TheseusRecord",
    "TheseusService",
    "phyllotaxis_coordinate",
    "tenant_storage_registry",
]
'''

GEODESIC_INIT = '''"""Geodesic: polytope geometry and routing used by Chronus.

Re-exports the 600-cell construction from chronus.quantum.geometric_polychoron.
The 600-cell is the regular 4-dimensional polytope with 120 vertices and H4
symmetry; the implementation's own invariants assert dimension 4. The H4
crossbar routing model (chronus.ns_dec) is available lazily as
chronus.geodesic.routing.
"""

import importlib

from chronus.quantum.geometric_polychoron import Cyclotomic5, Polychoron600Cell

__all__ = ["Cyclotomic5", "Polychoron600Cell", "routing"]


def __getattr__(name):
    if name == "routing":
        return importlib.import_module("chronus.ns_dec")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
'''

IGPU_INIT = '''"""iGPU: the Chronus execution-lane runtime.

Groups the execution lanes that exist in this repository: the CPU reference
path (chronus.execution.reference), the opt-in OpenCL adapters and their
packaged kernels (chronus.backends.opencl_pv, chronus.execution.opencl_backend,
chronus.kernels), the native C++ fold library (cpp/, built separately) and the
Zeckendorf hardware model (chronus.hw). The tensor representation used by the
Chronus service is exported as chronus.igpu.tensor. It ships inside the
Chronus distribution and is not published as a separate package.
"""

import importlib
from importlib import resources

__all__ = ["kernel_source", "tensor"]


def kernel_source(name: str) -> str:
    """Return the source text of a packaged OpenCL kernel, for example "pv_lattice.cl"."""
    if not name.endswith(".cl") or "/" in name or "\\\\" in name:
        raise ValueError("kernel name must be a bare *.cl file name")
    return resources.files("chronus.kernels").joinpath(name).read_text(encoding="utf-8")


def __getattr__(name):
    if name == "tensor":
        return importlib.import_module("chronus.igpu.tensor")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
'''

IGPU_TENSOR = '''"""chronus.igpu.tensor: the public export of the Chronus tensor representation.

The implementation lives in chronus.tensor; this module re-exports its public
API (the same objects) so iGPU-facing code and Chronus subsystems import it
from the iGPU namespace. TURING must not import it: the dependency runs from
Chronus to TURING, never the reverse. The representation is numerical (numpy)
and records truncation explicitly; it is not part of any exact path.
"""

from chronus import tensor as _tensor
from chronus.tensor.enhanced_representation import EnhancedTensorRepresentation

_PUBLIC = list(getattr(_tensor, "__all__", None) or [n for n in vars(_tensor) if not n.startswith("_")])
globals().update({_name: getattr(_tensor, _name) for _name in _PUBLIC})
__all__ = sorted(set(_PUBLIC) | {"EnhancedTensorRepresentation"})
'''

LAYOUT_TEST = '''"""Repository layout and namespace contracts (supervisor consolidation, 2026-11-11)."""

import importlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ARCHIVED_ROOT_FILES = (
    "cov_output.txt",
    "test_output.txt",
    "test_result.txt",
    "tree_output.txt",
    "filelist.txt",
    "pulvini_output.txt",
    "edge_output.txt",
    "build_ci_failed.log",
    ".coveragemp",
    "full_documentation.txt",
    "paradigm_shift.txt",
    "ARTIFACT_SUMMARY.md",
    "read_cov.py",
    "exact_primitive_library-v3.py",
    "qudit_qec.py",
    "production_hr_api.py",
    "production_hr_api-v2.py",
)


def test_archived_root_files_stay_out_of_the_root():
    assert [name for name in ARCHIVED_ROOT_FILES if (ROOT / name).exists()] == []


def test_one_turing_source_tree():
    assert not (ROOT / "src" / "turing").exists()
    turing = importlib.import_module("turing")
    expected = (ROOT / "packages" / "turing" / "src" / "turing").resolve()
    assert Path(turing.__file__).resolve().parent == expected


def test_turing_never_imports_chronus():
    pattern = re.compile(r"^\\s*(from|import)\\s+chronus\\b", re.M)
    offenders = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "packages" / "turing" / "src").rglob("*.py")
        if pattern.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_exact_layer_is_turing_exact():
    exact = importlib.import_module("turing.exact")
    for name in ("ZetaP", "MatrixZetaP", "StateZetaP", "StabilizerTableauZetaP"):
        assert hasattr(exact, name), name


def test_hermes_exports_the_acceleration_modules():
    for name in ("fourier", "state"):
        canonical = importlib.import_module("chronus.hermes." + name)
        implementation = importlib.import_module("chronus.acceleration." + name)
        assert canonical is implementation


def test_first_class_namespaces_reexport_the_same_objects():
    from chronus import geodesic, ovid, theseus
    from chronus.quantum.geometric_polychoron import Polychoron600Cell
    from chronus.security.ovid import OVIDStorage
    from chronus.storage.theseus import TheseusService

    assert ovid.OVIDStorage is OVIDStorage
    assert theseus.TheseusService is TheseusService
    assert geodesic.Polychoron600Cell is Polychoron600Cell


def test_igpu_tensor_export_is_the_chronus_tensor_class():
    from chronus.igpu import tensor as igpu_tensor
    from chronus.tensor.enhanced_representation import EnhancedTensorRepresentation

    assert igpu_tensor.EnhancedTensorRepresentation is EnhancedTensorRepresentation


def test_distribution_is_marked_private():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "hyba-chronus"' in text
    assert "Private :: Do Not Upload" in text
    assert "Private :: Do Not Upload" in (ROOT / "packages" / "turing" / "pyproject.toml").read_text(encoding="utf-8")
'''

NO_TEMP_WORKFLOWS = '''#!/usr/bin/env python3
"""Merge gate: temporary, diagnostic or scratch workflows must never reach main."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKERS = re.compile(r"temporary|not for merge|do not merge|never merge|scratch", re.IGNORECASE)


def offenders(root: Path = ROOT) -> list[str]:
    found = []
    for workflow in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        head = workflow.read_text(encoding="utf-8", errors="replace").splitlines()[:15]
        header = [line for line in head if line.startswith(("name:", "#"))]
        if (
            workflow.name.startswith("zz-")
            or "diagnostic" in workflow.name.lower()
            or any(MARKERS.search(line) for line in header)
        ):
            found.append(workflow.name)
    return found


if __name__ == "__main__":
    bad = offenders()
    if bad:
        print("Remove temporary workflows before merge: " + ", ".join(bad))
        sys.exit(1)
    print("No temporary workflows present.")
'''


def main() -> None:
    if run("git", "status", "--porcelain").strip():
        sys.exit("FAILED: working tree not clean")

    # 1. Root diagnostics (no owner; outputs only)
    diag = f"archive/diagnostics/{DATE}"
    for name in (
        "cov_output.txt", "test_output.txt", "test_result.txt", "tree_output.txt", "filelist.txt",
        "pulvini_output.txt", "edge_output.txt", "build_ci_failed.log", ".coveragemp",
        "full_documentation.txt", "paradigm_shift.txt", "ARTIFACT_SUMMARY.md", "read_cov.py",
    ):
        mv(name, f"{diag}/{name}")
    mv("src/turing/read_cov.py", f"{diag}/src_turing_read_cov.py")
    mv("src/turing/_rest.txt", f"{diag}/src_turing__rest.txt")
    write(f"{diag}/README.md", DIAG_README)

    # 2. TURING source snapshots
    mv("exact_primitive_library-v3.py", "archive/turing-sources/exact_primitive_library-v3.py")
    mv("qudit_qec.py", "archive/turing-sources/qudit_qec.py")
    write("archive/turing-sources/README.md", TURING_SOURCES_README)

    # 3. Root API entry points (canonical modules exist under chronus.service)
    mv("production_hr_api.py", "archive/root-entrypoints/production_hr_api.py")
    mv("production_hr_api-v2.py", "archive/root-entrypoints/production_hr_api-v2.py")
    write("archive/root-entrypoints/README.md", ENTRYPOINTS_README)
    edit(
        "tests/test_enhanced_tensor_representation_v2.py",
        'import importlib\n\nproduction_hr_api_v2_module = importlib.import_module("production_hr_api-v2")\n'
        "app = production_hr_api_v2_module.app\n",
        "from chronus.service.production_hr_api_v2 import app\n",
    )

    # 4. One TURING package: src/turing -> packages/turing/src/turing/exact
    if (ROOT / "packages/turing/src/turing/exact").exists():
        sys.exit("FAILED: packages/turing/src/turing/exact already exists")
    mv("src/turing", "packages/turing/src/turing/exact")
    internal = sum(rewrite_turing_imports(p) for p in sorted((ROOT / "packages/turing/src/turing/exact").rglob("*.py")))
    consumers = 0
    for top in ("tests", "src", "scripts", "benchmarks"):
        consumers += sum(rewrite_turing_imports(p) for p in sorted((ROOT / top).rglob("*.py")))
    print(f"turing.exact internal imports rewritten: {internal}; consumer imports rewritten: {consumers}")
    edit("packages/turing/src/turing/__init__.py", '__version__ = "0.1.0"', '__version__ = "0.2.0.dev0"')
    write("packages/turing/pyproject.toml", TURING_PYPROJECT)
    append("packages/turing/README.md", TURING_README_APPEND)
    append("docs/system-update/quantum-package-taxonomy.md", TAXONOMY_APPEND)

    # 5. First-class namespaces (additive re-exports; no implementation moves)
    write("src/chronus/hermes/__init__.py", HERMES_INIT)
    write("src/chronus/ovid/__init__.py", OVID_INIT)
    write("src/chronus/theseus/__init__.py", THESEUS_INIT)
    write("src/chronus/geodesic/__init__.py", GEODESIC_INIT)
    write("src/chronus/igpu/__init__.py", IGPU_INIT)
    write("src/chronus/igpu/tensor.py", IGPU_TENSOR)

    # 6. Distribution metadata and container build
    write("pyproject.toml", ROOT_PYPROJECT)
    edit("Dockerfile", "COPY src ./src\n", "COPY src ./src\nCOPY packages/turing/src ./packages/turing/src\n")
    edit("Dockerfile", "--find-links=/wheels chronus-quantum-igpu", "--find-links=/wheels hyba-chronus")

    # 7. Claim-token policy paths for files that moved
    policy_path = ROOT / "scripts/ci/claim_token_policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    moved = {
        "src/turing/physics/cayley.py": "packages/turing/src/turing/exact/physics/cayley.py",
        "src/turing/stabilizer/tableau.py": "packages/turing/src/turing/exact/stabilizer/tableau.py",
    }
    removed = {"exact_primitive_library-v3.py"}
    kept = []
    for entry in policy["allowlist"]:
        if entry["path"] in removed:
            print(f"claim allowlist: removed {entry['path']} (now under archive/, which the gate excludes)")
            continue
        if entry["path"] in moved:
            print(f"claim allowlist: {entry['path']} -> {moved[entry['path']]}")
            entry["path"] = moved[entry["path"]]
        kept.append(entry)
    policy["allowlist"] = kept
    policy_path.write_text(json.dumps(policy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    run("git", "add", "scripts/ci/claim_token_policy.json")

    # 8. Contract tests and the merge gate script
    write("tests/test_repository_layout.py", LAYOUT_TEST)
    write("scripts/ci/check_no_temporary_workflows.py", NO_TEMP_WORKFLOWS)

    print(run("git", "status", "--short"))


if __name__ == "__main__":
    main()

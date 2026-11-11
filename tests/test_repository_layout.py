"""Repository layout and namespace contracts (supervisor consolidation, 2026-11-11)."""

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
    pattern = re.compile(r"^\s*(from|import)\s+chronus\b", re.M)
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

"""Release-tooling UNIT tests; synthetic archives cannot certify the product."""

from email.message import EmailMessage
import hashlib
import importlib.util
import io
from pathlib import Path
import tarfile
import tomllib
import zipfile

import pytest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "salamander_release_builder", HERE / "build_and_verify.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def make_wheel(tmp, *, stable=False, corrupt=False, missing_typed=False, secret=False):
    project = {
        "name": "hyba-salamander-self-healing",
        "version": "1.0.0",
        "requires-python": ">=3.11",
    }
    sources = {
        name.replace(".", "/") + ".py": b"# unit archive fixture\n"
        for name in builder.REQUIRED_MODULES
        if name not in ("salamander", "al_haras")
    }
    sources.update({p + "/__init__.py": b"# unit archive fixture\n" for p in builder.PACKAGES})
    sources.update({p + "/py.typed": b"" for p in builder.PACKAGES})
    sources["salamander/_build_provenance.json"] = b"{}"
    inputs = {p: hashlib.sha256(b).hexdigest() for p, b in sources.items() if p.endswith(".py")}
    message = EmailMessage()
    for key, value in {
        "Metadata-Version": "2.4",
        "Name": project["name"],
        "Version": project["version"],
        "Requires-Python": ">=3.11",
        "License-Expression": "MIT",
    }.items():
        message[key] = value
    if stable:
        message["Classifier"] = "Development Status :: 5 - Production/Stable"
    sources["hyba_salamander_self_healing-1.0.0.dist-info/METADATA"] = message.as_bytes()
    sources["hyba_salamander_self_healing-1.0.0.dist-info/licenses/LICENSE"] = b"MIT fixture"
    if missing_typed:
        sources.pop("salamander/py.typed")
    if corrupt:
        sources["salamander/models.py"] += b"changed\n"
    if secret:
        sources["salamander/unit_fixture.txt"] = b"ghp_" + b"x" * 32
    path = tmp / "unit-fixture.whl"
    with zipfile.ZipFile(path, "w") as archive:
        for name, contents in sources.items():
            archive.writestr(name, contents)
    return path, project, inputs


def test_archive_unit_fixture_accepts_complete_product_manifest(tmp_path):
    path, project, inputs = make_wheel(tmp_path)
    result = builder.inspect_wheel(path, project=project, inputs=inputs)
    assert result["passed"]
    assert set(builder.REQUIRED_MODULES) <= set(result["modules"])


@pytest.mark.parametrize(
    "defect,gate",
    [
        ("stable", "not_production_stable_claim"),
        ("corrupt", "source_equivalence"),
        ("missing_typed", "typed_markers"),
        ("secret", "secret_patterns"),
    ],
)
def test_archive_defects_are_not_green(tmp_path, defect, gate):
    path, project, inputs = make_wheel(tmp_path, **{defect: True})
    result = builder.inspect_wheel(path, project=project, inputs=inputs)
    assert not result["passed"]
    assert result["checks"][gate] is False


def test_unrelated_package_cannot_enter_distribution(tmp_path):
    path, project, inputs = make_wheel(tmp_path)
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("chronus/__init__.py", b"")
    assert not builder.inspect_wheel(path, project=project, inputs=inputs)["checks"][
        "product_boundary"
    ]


@pytest.mark.parametrize(
    "name,member_type",
    [
        ("../escape", tarfile.REGTYPE),
        ("/absolute", tarfile.REGTYPE),
        ("unit/link", tarfile.SYMTYPE),
        ("unit/hardlink", tarfile.LNKTYPE),
    ],
)
def test_unsafe_source_archives_refused(tmp_path, name, member_type):
    path = tmp_path / "unit.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        member = tarfile.TarInfo(name)
        member.type = member_type
        member.linkname = "outside"
        member.size = 0
        archive.addfile(member, io.BytesIO(b""))
    with pytest.raises(RuntimeError, match="unsafe"):
        builder.unpack_sdist(path, tmp_path / "extract")
    assert not (tmp_path / "escape").exists()


def test_staging_refuses_unreviewed_data_instead_of_silently_dropping(tmp_path):
    for package in builder.PACKAGES:
        p = tmp_path / package
        p.mkdir()
        (p / "__init__.py").write_text("")
    (tmp_path / "salamander/runtime-secret.key").write_text("unit")
    with pytest.raises(RuntimeError, match="unreviewed product data"):
        builder.source_files(tmp_path)


def test_installability_is_not_production_readiness():
    status = builder.verdict(
        {g: "PASSED" for g in builder.RELEASE_GATES},
        {"production_ready": False, "gates": {"a": "UNAVAILABLE"}},
    )
    assert status["artifact_verified"]
    assert not status["publishable"]
    assert not status["published"]


def test_empty_or_failed_gates_cannot_pass():
    for gates in ({}, {"archive": "FAILED"}, {"archive": "UNAVAILABLE"}):
        assert not builder.verdict(gates, {})["artifact_verified"]
    assert not builder.verdict({"archive": "PASSED"}, {"production_ready": True, "gates": {}})[
        "publishable"
    ]


def test_single_good_gate_does_not_qualify_whole_build():
    assert not builder.verdict({"source_identity": "PASSED"}, {})["artifact_verified"]


def test_build_config_matches_import_version_and_boundaries():
    cfg = tomllib.loads((HERE / "pyproject.toml").read_text())
    from salamander import __version__

    assert cfg["project"]["version"] == __version__ == "1.0.0"
    assert cfg["project"]["license"] == "MIT"
    assert cfg["project"]["license-files"] == ["LICENSE"]
    assert "Development Status :: 5 - Production/Stable" not in cfg["project"]["classifiers"]
    assert cfg["tool"]["setuptools"]["packages"]["find"]["include"] == ["salamander*", "al_haras*"]


def test_bundled_cedr_has_its_signature_dependency_declared():
    import tomllib
    from pathlib import Path

    config = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
    assert "cryptography>=46,<51" in config["project"]["dependencies"]

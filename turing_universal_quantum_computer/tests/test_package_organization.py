"""Executable package/reproducibility boundaries, not a claim of a finished paper."""

from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import pytest

PROJECT = Path(__file__).resolve().parents[1]


def module(name):
    path = PROJECT / "experiments" / (name + ".py")
    spec = importlib.util.spec_from_file_location("turing_experiment_" + name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


@pytest.fixture
def experiment(tmp_path):
    runner = module("run_experiment")
    config_path = PROJECT / "experiments/configs/exact_package_validation.json"
    config = json.loads(config_path.read_text())
    config["repetitions"] = 1
    selected = tmp_path / "config.json"
    selected.write_text(json.dumps(config))
    # Explicit dev flags: test checkout/ZIP state must not be silently relabelled.
    path = runner.run(selected, tmp_path / "results", allow_unversioned=True, allow_dirty=True)
    return runner, path


def test_single_package_alias_and_existing_pipeline():
    from turing_universal_quantum_computer import TuringPipeline, QuantumPipeline, VQCPipeline

    assert TuringPipeline is QuantumPipeline
    assert TuringPipeline is not VQCPipeline
    assert not (PROJECT.parent / "src/advanced_quantum_pipeline").exists()


def test_complete_real_experiment_manifest(experiment):
    _, path = experiment
    data = json.loads(path.read_text())
    assert data["status"] == "completed" and len(data["measurements"]) == 3
    assert data["source"]["state"] in {"clean", "dirty", "unversioned"}
    if data["source"]["state"] != "clean":
        assert data["qualification"] == "development_only"
    for measurement in data["measurements"]:
        assert measurement["verified"] is True
        assert measurement["wall_time_ns"] >= 0
        assert all(j["evidence"]["pipeline_report"]["certificate"] for j in measurement["jobs"])


def test_analysis_deterministic_from_manifest(experiment, tmp_path):
    _, path = experiment
    analyzer = module("analyze_results")
    first = analyzer.generate(path, tmp_path / "one")
    second = analyzer.generate(path, tmp_path / "two")
    assert [p.read_bytes() for p in first] == [p.read_bytes() for p in second]
    assert (
        "development_only" in first[0].read_text() or "clean_commit_bound" in first[0].read_text()
    )


@pytest.mark.parametrize("mutation", ["value", "failed", "coverage", "reference"])
def test_analysis_rejects_modified_or_incomplete_results(experiment, tmp_path, mutation):
    runner, path = experiment
    analyzer = module("analyze_results")
    data = json.loads(path.read_text())
    if mutation == "value":
        data["measurements"][0]["value"] = 100.0  # unchanged digest must be rejected
    else:
        if mutation == "failed":
            data["status"] = "failed"
        if mutation == "coverage":
            data["measurements"].pop()
        if mutation == "reference":
            data["measurements"][0]["exact_coefficients"] = ["9", "0"]
            data["measurements"][0]["reference_coefficients"] = ["9", "0"]
        data.pop("manifest_digest")
        data["manifest_digest"] = runner.digest(data)
    bad = tmp_path / "modified.json"
    bad.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        analyzer.validate_manifest(bad)


def test_unversioned_source_does_not_invent_commit(tmp_path):
    runner = module("run_experiment")
    identity = runner.source_identity(tmp_path)
    assert identity == {"commit": None, "state": "unversioned", "dirty": None}


def test_default_rejects_unversioned_source(monkeypatch, tmp_path):
    runner = module("run_experiment")
    monkeypatch.setattr(
        runner,
        "source_identity",
        lambda path: {"state": "unversioned", "commit": None, "dirty": None},
    )
    with pytest.raises(RuntimeError, match="no commit identity"):
        runner.run(PROJECT / "experiments/configs/exact_package_validation.json", tmp_path)


def test_default_rejects_dirty_source(monkeypatch, tmp_path):
    runner = module("run_experiment")
    monkeypatch.setattr(
        runner,
        "source_identity",
        lambda path: {"state": "dirty", "commit": "a" * 40, "dirty": True},
    )
    with pytest.raises(RuntimeError, match="clean checkout"):
        runner.run(PROJECT / "experiments/configs/exact_package_validation.json", tmp_path)


def test_failed_execution_retains_diagnostic_manifest(monkeypatch, tmp_path):
    runner = module("run_experiment")

    def fail(*args):
        raise RuntimeError("controlled experiment failure")

    monkeypatch.setattr(runner, "evaluate", fail)
    with pytest.raises(RuntimeError, match="diagnostic manifest"):
        runner.run(
            PROJECT / "experiments/configs/exact_package_validation.json",
            tmp_path,
            allow_unversioned=True,
            allow_dirty=True,
        )
    files = list(tmp_path.glob("exact_package_validation-*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["status"] == "failed" and data["failure"]["type"] == "RuntimeError"


def test_config_rejects_unimplemented_case_and_unknown_settings(tmp_path):
    runner = module("run_experiment")
    config = json.loads((PROJECT / "experiments/configs/exact_package_validation.json").read_text())
    config["cases"] = ["invented_case"]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        runner.load_config(path)
    config["cases"] = ["bell_z0"]
    config["execution"]["imaginary_optimization_level"] = 100
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError):
        runner.load_config(path)


def test_dependency_lock_and_metadata_are_real():
    import tomllib

    project = tomllib.loads((PROJECT / "pyproject.toml").read_text())
    lock = tomllib.loads((PROJECT / "uv.lock").read_text())
    assert project["project"]["name"] == "hyba-turing-vqc"
    assert any(
        p["name"] == "hyba-kellogg-tensor"
        and p["source"].get("directory") == "../packaging/kellogg-tensor"
        for p in lock["package"]
    )
    for directory in ("docs", "experiments", "results", "paper"):
        assert (PROJECT / directory).is_dir()


@pytest.mark.parametrize("kind", ["parent", "absolute", "symlink"])
def test_sdist_extraction_rejects_unsafe_members(tmp_path, kind):
    import io
    import tarfile

    qualifier = module("qualify_artifacts")
    archive = tmp_path / "unsafe.tar.gz"
    member = tarfile.TarInfo(
        {"parent": "../escape.py", "absolute": "/escape.py", "symlink": "package/link"}[kind]
    )
    if kind == "symlink":
        member.type = tarfile.SYMTYPE
        member.linkname = "/outside"
    else:
        member.size = 1
    with tarfile.open(archive, "w:gz") as stream:
        stream.addfile(member, None if kind == "symlink" else io.BytesIO(b"x"))
    destination = tmp_path / "unpacked"
    destination.mkdir()
    with pytest.raises(ValueError):
        qualifier.unpack_sdist(archive, destination)
    assert not (tmp_path / "escape.py").exists()


def test_wheel_content_parity_distinguishes_container_timestamps(tmp_path):
    import zipfile

    qualifier = module("qualify_artifacts")
    paths = [tmp_path / "one.whl", tmp_path / "two.whl"]
    for index, path in enumerate(paths):
        with zipfile.ZipFile(path, "w") as archive:
            item = zipfile.ZipInfo("package/__init__.py", date_time=(2020 + index, 1, 1, 0, 0, 0))
            archive.writestr(item, b"VALUE = 1\n")
    assert paths[0].read_bytes() != paths[1].read_bytes()
    assert qualifier.wheel_content(paths[0]) == qualifier.wheel_content(paths[1])
    assert qualifier.container_metadata(paths[0]) != qualifier.container_metadata(paths[1])


def test_generated_reference_matches_importable_candidate():
    generator = module("generate_api_reference")
    assert generator.render() == (PROJECT / "docs/reference.md").read_text()

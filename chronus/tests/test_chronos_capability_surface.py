"""Completeness and distribution gates for the combined Chronos surface."""

from __future__ import annotations

from pathlib import Path
import tomllib

from chronus.v33 import audit_capability_surface, load_capability_manifest


def test_every_manifested_chronos_symbol_is_importable():
    report = audit_capability_surface()
    manifest = load_capability_manifest()

    assert report.ok
    assert report.modules == len(manifest)
    assert report.classes == sum(len(row.get("classes", [])) for row in manifest)
    assert report.functions == sum(len(row.get("functions", [])) for row in manifest)
    assert report.modules >= 50
    assert report.classes >= 90
    assert report.functions >= 90


def test_combined_surface_is_shipped_in_installed_distribution():
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    setuptools = config["tool"]["setuptools"]
    packages = set(setuptools["packages"])
    package_data = setuptools["package-data"]

    required_packages = {
        "chronos",
        "chronos.academic",
        "chronus.v33",
        "chronus.v33.academic",
        "chronus.v33.compression",
        "chronus.v33.control",
        "chronus.v33.environment",
        "chronus.v33.fields",
        "chronus.v33.graphics",
        "chronus.v33.memory",
        "chronus.v33.theory",
        "chronus.v33.benchmarks",
        "chronus.v33.examples",
    }
    assert required_packages <= packages
    assert "CAPABILITY_MANIFEST.json" in package_data["chronus.v33"]
    assert "docs/*.md" in package_data["chronus.v33"]
    assert "benchmarks/*.json" in package_data["chronus.v33"]


def test_deprecated_facade_exposes_the_completeness_gate():
    import chronos

    assert chronos.audit_capability_surface is audit_capability_surface

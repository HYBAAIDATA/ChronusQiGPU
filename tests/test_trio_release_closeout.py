"""Focused metadata/staging/archive regressions; not product qualification."""
import importlib.util
from pathlib import Path
import tempfile
import tomllib
import unittest
import zipfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(relative, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ownership = load("packaging/check_wheel_ownership.py", "ownership")
kellogg = load("packaging/kellogg-tensor/build_and_verify.py", "kellogg_builder")
turing = load("packaging/turing/build_wheel.py", "turing_builder")


class TrioCloseoutTests(unittest.TestCase):
    def test_canonical_metadata_preserves_dependencies(self):
        for relative, name, dependencies in (
            ("packaging/kellogg-tensor/pyproject.toml", "hyba-kellogg-tensor", ["numpy>=1.26,<3"]),
            ("turing_universal_quantum_computer/pyproject.toml", "hyba-turing-vqc",
             ["numpy>=1.26,<3", "sympy>=1.12,<2", "hyba-kellogg-tensor>=1.0"]),
            ("chronus/packaging/chronus-igpu/pyproject.toml", "hyba-chronus-igpu",
             ["numpy>=1.26,<3", "hyba-chronos-mathematics>=1.0",
              "hyba-kellogg-tensor>=1.0", "hyba-chronos-one-igpu>=1.0"]),
        ):
            with self.subTest(name=name):
                project = tomllib.loads((ROOT / relative).read_text())["project"]
                self.assertEqual(project["name"], name)
                self.assertEqual(project["dependencies"], dependencies)
                for url in project["urls"].values():
                    self.assertTrue(url.startswith("https://github.com/PhiEnterprise1/EuclidPhiEnterprise"))

    def test_builder_repository_identity(self):
        self.assertEqual(turing.REPOSITORY, "PhiEnterprise1/EuclidPhiEnterprise")
        self.assertEqual(kellogg.REPOSITORY, turing.REPOSITORY)

    def stage_fixture(self, manifest):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            source = repo / "kellogg"
            here = repo / "packaging/kellogg-tensor"
            source.mkdir(parents=True)
            here.mkdir(parents=True)
            (source / "__init__.py").write_text('__version__ = "1.0.0"\n')
            (repo / "LICENSE").write_text("MIT")
            (here / "README.md").write_text("fixture, not product source")
            (here / "pyproject.toml").write_text(manifest)
            with patch.object(kellogg, "REPO", repo), patch.object(kellogg, "HERE", here):
                staged = kellogg.stage(Path(tmp) / "work")
            cfg = tomllib.loads((staged / "pyproject.toml").read_text())
            target = staged / cfg["tool"]["setuptools"]["package-dir"]["kellogg"]
            self.assertTrue(target.is_relative_to(staged))
            self.assertTrue((target / "__init__.py").is_file())
            self.assertEqual((here / "pyproject.toml").read_text(), manifest)

    def test_kellogg_stage_is_self_contained(self):
        self.stage_fixture((ROOT / "packaging/kellogg-tensor/pyproject.toml").read_text())

    def test_kellogg_stage_rejects_unreviewed_mapping(self):
        with self.assertRaisesRegex(RuntimeError, "package-dir contract changed"):
            self.stage_fixture('[tool.setuptools]\npackage-dir = {"kellogg" = "unexpected"}\n')

    def wheel(self, directory, product, payload):
        wheel = Path(directory) / (product.replace("-", "_") + "-1.0.0-py3-none-any.whl")
        with zipfile.ZipFile(wheel, "w") as archive:
            archive.writestr(product.replace("-", "_") + "-1.0.0.dist-info/METADATA",
                             f"Name: {product}\nVersion: 1.0.0\n")
            for name in payload:
                archive.writestr(name, "fixture")
        return wheel

    def test_disjoint_wheels_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = ownership.audit([self.wheel(tmp, "hyba-kellogg-tensor", ["kellogg/a.py"]),
                                      self.wheel(tmp, "hyba-turing-vqc", ["turing/a.py"])])
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["release_qualification"], "NOT_EVALUATED")

    def test_same_byte_collision_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = ownership.audit([self.wheel(tmp, "hyba-pythia-mining", ["chronus/a.py"]),
                                      self.wheel(tmp, "hyba-chronus-igpu", ["chronus/a.py"])])
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("site/chronus/a.py", result["collisions"])

    def test_data_purelib_collision_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = ownership.audit([self.wheel(tmp, "a", ["x.py"]),
                                      self.wheel(tmp, "b", ["b-1.0.0.data/purelib/x.py"])])
            self.assertEqual(result["status"], "FAIL")

    def test_consumer_bundle_rejected_even_without_path_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = ownership.audit([self.wheel(tmp, "hyba-pythia-consumer", ["bundle/a.py"]),
                                      self.wheel(tmp, "hyba-chronus-igpu", ["chronus/a.py"])])
            self.assertEqual(result["status"], "FAIL")
            self.assertIn("consumer bundle", result["errors"][0])

    def test_duplicate_distribution_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            wheel = self.wheel(tmp, "hyba-kellogg-tensor", ["kellogg/a.py"])
            self.assertEqual(ownership.audit([wheel, wheel])["status"], "FAIL")

    def test_unsafe_member_rejected(self):
        with self.assertRaises(ValueError):
            ownership.installed_path("../outside.py")


if __name__ == "__main__":
    unittest.main()

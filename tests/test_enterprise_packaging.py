"""Hermetic packaging unit tests; synthetic wheels are not release artifacts."""

import importlib.util
import hashlib
import json
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location(
    "enterprise_builder", Path(__file__).resolve().parents[1] / "scripts/build_standalone_wheel.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


verifier_spec = importlib.util.spec_from_file_location(
    "installed_verifier", Path(__file__).resolve().parents[1] / "scripts/verify_clean_install.py"
)
verifier = importlib.util.module_from_spec(verifier_spec)
verifier_spec.loader.exec_module(verifier)


class EnterprisePackaging(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def project(self, name, body=""):
        directory = self.root / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "__init__.py").write_text(body)
        return directory

    def wheel(self, *, name="euclid-engine", secret=False, omit=None):
        path = self.root / "synthetic.whl"
        required = [
            "euclid/runtime.py",
            "Intelligence/capability_fabric.py",
            "euclid/capabilities/empirical_state_bridge.py",
            "euclid/capabilities/empirical_runtime.py",
            "euclid/capabilities/empirical_recovery.py",
            "al_haras/audit.py",
            "aethel/enterprise/lifecycle.py",
            "euclid/_artifact_provenance.json",
        ]
        with zipfile.ZipFile(path, "w") as archive:
            for member in required:
                if member != omit:
                    archive.writestr(member, "{}" if member.endswith("json") else "# fixture\n")
            archive.writestr(
                "euclid_engine-1.0.0.dist-info/METADATA",
                f"Metadata-Version: 2.1\nName: {name}\nVersion: 1.0.0\n",
            )
            if secret:
                archive.writestr("euclid/fixture.txt", "-----BEGIN PRIVATE KEY-----")
        return path

    def test_inspection_accepts_only_dedicated_enterprise_identity(self):
        with self.assertRaises(RuntimeError):
            builder.inspect_wheel(self.wheel(name="hyba-pythia-mining"))
        self.assertIn("euclid/runtime.py", builder.inspect_wheel(self.wheel()))

    def test_missing_runtime_member_rejected(self):
        with self.assertRaises(RuntimeError):
            builder.inspect_wheel(self.wheel(omit="euclid/capabilities/empirical_runtime.py"))

    def test_secret_pattern_rejected(self):
        with self.assertRaises(RuntimeError):
            builder.inspect_wheel(self.wheel(secret=True))

    def test_missing_seed_never_silently_skipped(self):
        (self.root / "pyproject.toml").write_text("[project]\nname='fixture'\n")
        destination = self.root / "staged"
        destination.mkdir()
        with patch.object(builder, "REPO", self.root), patch.object(builder, "SEEDS", ("missing",)):
            with self.assertRaises(FileNotFoundError):
                builder.stage(destination)

    def test_transitive_local_imports_and_assets_preserved(self):
        (self.root / "pyproject.toml").write_text("[project]\nname='fixture'\n")
        self.project("seed", "import dependency\n")
        dependency = self.project("dependency", "import leaf\n")
        (dependency / "config.json").write_text('{"fixture":true}')
        (dependency / "tests").mkdir()
        (dependency / "tests/test_bad.py").write_text("raise RuntimeError('not shipped')")
        (self.root / "leaf.py").write_text("VALUE = 1\n")
        (self.root / "turing_core.py").write_text("VALUE = 1\n")
        (self.root / "pythia_turing_math.py").write_text("VALUE = 1\n")
        destination = self.root / "staged"
        destination.mkdir()
        with patch.object(builder, "REPO", self.root), patch.object(builder, "SEEDS", ("seed",)):
            result = builder.stage(destination)
        self.assertIn("dependency", result)
        self.assertTrue((destination / "leaf.py").is_file())
        self.assertTrue((destination / "turing_core.py").is_file())
        self.assertFalse((destination / "turing_core").exists())
        self.assertTrue((destination / "dependency/config.json").is_file())
        self.assertFalse((destination / "dependency/tests").exists())

    def test_python_package_mapping_is_honored(self):
        location = self.project("chronus/lucas")
        with patch.object(builder, "REPO", self.root):
            self.assertEqual(builder.local_source("lucas", {"lucas": "chronus/lucas"}), location)

    def test_real_build_pipeline_on_synthetic_committed_fixture(self):
        # Exercises setuptools/build/pip, not an EUCLID runtime qualification.
        source = self.root / "fixture-repo"
        source.mkdir()
        (source / "pyproject.toml").write_text("[project]\nname='fixture'\n")
        (source / "LICENSE").write_text("Synthetic packaging test fixture only.\n")
        for name in builder.SEEDS:
            directory = source / name
            directory.mkdir()
            (directory / "__init__.py").write_text("")
        required = (
            "euclid/runtime.py",
            "Intelligence/capability_fabric.py",
            "euclid/capabilities/empirical_state_bridge.py",
            "euclid/capabilities/empirical_runtime.py",
            "euclid/capabilities/empirical_recovery.py",
            "al_haras/audit.py",
            "aethel/enterprise/lifecycle.py",
            "scripts/verify_clean_install.py",
        )
        for relative in required:
            path = source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            (path.parent / "__init__.py").touch()
            path.write_text("# Synthetic test fixture, not a product implementation.\n")
        (source / "turing_core.py").write_text("")
        (source / "pythia_turing_math.py").write_text("")
        assets = source / "euclid/nonpackage-assets"
        assets.mkdir()
        (assets / "fixture.json").write_text('{"fixture": true}')
        # Three synthetic owner artifacts exercise build plumbing only.
        owner = source / "kellogg"
        owner.mkdir()
        (owner / "__init__.py").write_text('__version__ = "1.0.0"\n')
        for distribution, project, package in (
            ("hyba-kellogg-tensor", "packaging/kellogg-tensor", "kellogg"),
            (
                "hyba-turing-vqc",
                "turing_universal_quantum_computer",
                "turing_universal_quantum_computer",
            ),
        ):
            location = source / project
            location.mkdir(parents=True, exist_ok=True)
            if package != "kellogg":
                (location / package).mkdir()
                (location / package / "__init__.py").write_text('VERSION = "1.0.0"\n')
            mapping = '{"kellogg" = "../../kellogg"}' if package == "kellogg" else '{"" = "."}'
            (location / "pyproject.toml").write_text(
                '[build-system]\nrequires=["setuptools>=68", "wheel"]\nbuild-backend="setuptools.build_meta"\n'
                f'[project]\nname="{distribution}"\nversion="1.0.0"\n'
                f'[tool.setuptools]\npackages=["{package}"]\npackage-dir={mapping}\n'
            )
        for args in (
            ("init",),
            ("add", "."),
            (
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-m",
                "synthetic packaging fixture",
            ),
        ):
            subprocess.run(["git", *args], cwd=source, check=True, capture_output=True)
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=source, check=True, text=True, capture_output=True
        ).stdout.strip()
        (source / ".git/info/exclude").write_text("euclid/ambient.py\n")
        (source / "euclid/ambient.py").write_text("# Ignored local pollution must never ship.\n")
        wheelhouse = self.root / "empty-wheelhouse"
        wheelhouse.mkdir()
        output = self.root / "output"
        with patch.object(builder, "REPO", source), patch.object(builder, "DEPENDENCIES", ()):
            wheel = builder.stage_and_build(
                expected_commit=commit, output_dir=output, offline=True, wheelhouse=wheelhouse
            )
        manifest = json.loads((output / "build-manifest.json").read_text())
        self.assertEqual(
            set(manifest["owned_distributions"]),
            {"euclid-engine", "hyba-turing-vqc", "hyba-kellogg-tensor"},
        )
        self.assertEqual(len(list(output.glob("*.whl"))), 3)
        self.assertEqual(manifest["source_commit"], commit)
        self.assertEqual(manifest["wheel_sha256"], hashlib.sha256(wheel.read_bytes()).hexdigest())
        with zipfile.ZipFile(wheel) as archive:
            self.assertIn("euclid/nonpackage-assets/fixture.json", archive.namelist())
            self.assertNotIn("euclid/ambient.py", archive.namelist())
            provenance = json.loads(archive.read("euclid/_artifact_provenance.json"))
        self.assertEqual(provenance["source_commit"], commit)

    def test_installed_provenance_tampering_and_missing_owners_refused(self):
        from types import SimpleNamespace

        path = self.root / "member.py"
        path.write_text("# original")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        dist = SimpleNamespace(version="1.0.0", locate_file=lambda name: self.root / name)
        owners = {
            name: {"wheel": name + ".whl", "members": {"member.py": digest}}
            for name in ("euclid-engine", "hyba-turing-vqc", "hyba-kellogg-tensor")
        }
        manifest = {"source_commit": "candidate", "owned_distributions": owners}
        with patch.object(verifier.importlib.metadata, "distribution", return_value=dist):
            self.assertEqual(len(verifier.verify_installed_members(manifest, "candidate")), 3)
            with self.assertRaises(RuntimeError):
                verifier.verify_installed_members(manifest, "wrong-commit")
            path.write_text("# tampered")
            with self.assertRaises(RuntimeError):
                verifier.verify_installed_members(manifest, "candidate")
        manifest["owned_distributions"].pop("hyba-turing-vqc")
        with self.assertRaises(RuntimeError):
            verifier.verify_installed_members(manifest, "candidate")

    def test_vendored_owner_rejected(self):
        wheel = self.wheel()
        with zipfile.ZipFile(wheel, "a") as archive:
            archive.writestr("kellogg/__init__.py", "# must belong to canonical owner")
        with self.assertRaises(RuntimeError):
            builder.inspect_wheel(wheel)

    def test_member_overlap_rejected(self):
        a, b = self.root / "a.whl", self.root / "b.whl"
        for wheel in (a, b):
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr("kellogg/__init__.py", "# duplicate")
        with self.assertRaises(RuntimeError):
            builder.reject_wheel_overlaps([a, b])

    def test_external_owners_not_vendored_by_import_closure(self):
        (self.root / "pyproject.toml").write_text("[project]\nname='fixture'\n")
        self.project("seed", "import kellogg\nimport turing_universal_quantum_computer\n")
        self.project("kellogg")
        self.project("turing_universal_quantum_computer")
        (self.root / "turing_core.py").write_text("")
        (self.root / "pythia_turing_math.py").write_text("")
        with patch.object(builder, "REPO", self.root), patch.object(builder, "SEEDS", ("seed",)):
            builder.stage(self.root / "staged")
        self.assertFalse((self.root / "staged/kellogg").exists())
        self.assertFalse((self.root / "staged/turing_universal_quantum_computer").exists())

    def test_dirty_source_or_wrong_commit_refused(self):
        from types import SimpleNamespace

        with patch.object(builder, "sh", return_value=SimpleNamespace(stdout="actual\n")):
            with self.assertRaises(RuntimeError):
                builder.source_commit("different")
        replies = [SimpleNamespace(stdout="actual\n"), SimpleNamespace(stdout=" M source.py\n")]
        with patch.object(builder, "sh", side_effect=replies):
            with self.assertRaises(RuntimeError):
                builder.source_commit("actual")


if __name__ == "__main__":
    unittest.main()

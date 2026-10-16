"""Exercise actual Git ignore/index behavior without importing the runtime.

These fixtures are empty tracking probes, NOT recovered PHILOS model definitions.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
IGNORE = Path(os.environ.get("PHILOS_GITIGNORE_UNDER_TEST", str(ROOT / ".gitignore")))
MODEL_SOURCES = (
    "__init__.py", "manifest.py", "telemetry.py", "substrate.py",
    "candidate.py", "qualification.py", "condensation.py",
)


class EmergenceModelTrackingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        shutil.copyfile(IGNORE, self.root / ".gitignore")
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True)

    def touch(self, rel):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# tracking probe, not an implementation\n")
        return rel

    def test_each_python_contract_is_not_ignored(self):
        for name in MODEL_SOURCES:
            with self.subTest(source=name):
                rel = self.touch("euclid/emergence/models/" + name)
                result = self.git("check-ignore", "--quiet", rel)
                self.assertEqual(result.returncode, 1, result.stderr)

    def test_normal_git_add_tracks_all_contract_probes_without_force(self):
        paths = [self.touch("euclid/emergence/models/" + name) for name in MODEL_SOURCES]
        result = self.git("add", "--", *paths)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("ls-files").stdout.splitlines(), sorted(paths))

    def test_model_artifacts_and_package_cache_stay_ignored(self):
        for rel in ("models/weights.bin", "other/models/trained.py",
                    "euclid/emergence/models/weights.bin",
                    "euclid/emergence/models/__pycache__/manifest.pyc",
                    ".pnpm-store/cache.bin"):
            with self.subTest(artifact=rel):
                self.touch(rel)
                result = self.git("check-ignore", "--quiet", rel)
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

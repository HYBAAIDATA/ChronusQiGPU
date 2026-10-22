"""Offline recovery tests; never import recovered application modules."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from recovery.hyba_data.package import build, safe_path


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        (self.source / "hyba_data").mkdir(parents=True)
        (self.source / "hyba_data/a.py").write_bytes(b"original\n")
        self.manifest = self.root / "manifest.json"
        self.output = self.root / "output.zip"
        self.entries = [{"path": "hyba_data/a.py",
                         "sha256": hashlib.sha256(b"original\n").hexdigest()}]

    def write_manifest(self):
        self.manifest.write_text(json.dumps({"expected_files": len(self.entries),
                                              "files": self.entries}))

    def run_build(self, partial=False):
        self.write_manifest()
        return build(self.manifest, self.source, self.output, partial)

    def test_complete(self):
        report = self.run_build()
        self.assertTrue(report["complete"])
        with zipfile.ZipFile(self.output) as archive:
            self.assertEqual(archive.read("hyba_data/a.py"), b"original\n")

    def test_reproducible(self):
        self.run_build()
        first = self.output.read_bytes()
        self.run_build()
        self.assertEqual(first, self.output.read_bytes())

    def test_missing_refused(self):
        self.entries.append({"path": "hyba_data/missing.py"})
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            self.run_build()
        self.assertFalse(self.output.exists())

    def test_partial_explicit(self):
        self.entries.append({"path": "hyba_data/missing.py"})
        report = self.run_build(True)
        self.assertFalse(report["complete"])
        self.assertEqual(report["missing_files"], ["hyba_data/missing.py"])

    def test_tampering_refused(self):
        (self.source / "hyba_data/a.py").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.run_build()

    def test_duplicate_refused(self):
        self.entries *= 2
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.run_build()

    def test_unsafe_paths(self):
        for name in ("/absolute", "hyba_data/../secret", "hyba_data//a.py",
                     "hyba_data/./a.py", "hyba_data\\a.py", "C:/file", "other/a.py"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_path(name)

    def test_symlink_refused(self):
        (self.source / "hyba_data/link.py").symlink_to(self.source / "hyba_data/a.py")
        self.entries.append({"path": "hyba_data/link.py"})
        with self.assertRaisesRegex(ValueError, "Symlink"):
            self.run_build()

    def test_unknown_files_excluded(self):
        (self.source / "hyba_data/unindexed.py").write_bytes(b"not included")
        self.run_build()
        with zipfile.ZipFile(self.output) as archive:
            self.assertNotIn("hyba_data/unindexed.py", archive.namelist())

    def test_existing_output_preserved_on_failure(self):
        self.output.write_bytes(b"previous")
        self.entries.append({"path": "hyba_data/missing.py"})
        with self.assertRaises(ValueError):
            self.run_build()
        self.assertEqual(self.output.read_bytes(), b"previous")

    def test_inventory_count_checked(self):
        self.write_manifest()
        manifest = json.loads(self.manifest.read_text())
        manifest["expected_files"] += 1
        self.manifest.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "count mismatch"):
            build(self.manifest, self.source, self.output)

    def test_output_cannot_replace_source(self):
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "overwrite"):
            build(self.manifest, self.source, self.source / "hyba_data/a.py")


if __name__ == "__main__":
    unittest.main()

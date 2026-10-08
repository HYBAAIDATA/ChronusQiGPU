"""Hermetic packaging guard tests; never product or registry qualification."""
import importlib.util
import json
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("storage_packaging",ROOT / "packaging/storage-release/build_and_verify.py")
M=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class StoragePreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        (self.root / "aethel").mkdir()
        (self.root / "aethel/__init__.py").write_text('"canonical fixture"\n')
        (self.root / "aethel/capabilities.json").write_text('{"scope":"fixture"}')
        self.inventory=M.source_inventory(self.root,"aethel")

    def wheel(self, entries=None):
        p=self.root / "fixture.whl"
        with zipfile.ZipFile(p,"w") as z:
            for name in self.inventory["files_sha256"]:
                z.write(self.root / name,name)
            for name,data in (entries or {}).items():z.writestr(name,data)
        return p

    def test_byte_preserving_fixture(self):
        self.assertEqual(M.inspect_wheel(self.wheel(),self.inventory)["source_identity"],"PASS")

    def test_foreign_product_rejected(self):
        with self.assertRaises(RuntimeError):
            M.inspect_wheel(self.wheel({"kellogg/__init__.py":""}),self.inventory)

    def test_duplicate_namespace_in_ovid_rejected(self):
        inv={"owned_package":"hyba_db","files_sha256":{}}
        with self.assertRaises(RuntimeError):
            M.inspect_wheel(self.wheel(),inv)

    def test_modified_canonical_source_rejected(self):
        p=self.root / "modified.whl"
        with zipfile.ZipFile(p,"w") as z:z.writestr("aethel/__init__.py","changed")
        with self.assertRaises(RuntimeError):M.inspect_wheel(p,self.inventory)

    def test_missing_manifest_rejected(self):
        p=self.root / "missing.whl"
        with zipfile.ZipFile(p,"w") as z:z.write(self.root / "aethel/__init__.py","aethel/__init__.py")
        with self.assertRaises(RuntimeError):M.inspect_wheel(p,self.inventory)

    def test_secret_shaped_archive_rejected(self):
        p=self.wheel({"fixture.dist-info/secret.txt":"ghp_"+"A"*40})
        with self.assertRaises(RuntimeError):M.inspect_wheel(p,self.inventory)

    def test_missing_source_rejected(self):
        with self.assertRaises(RuntimeError):M.source_inventory(self.root,"absent")

    def test_skipped_required_suite_rejected(self):
        p=self.root / "tests.xml"
        p.write_text('<testsuite tests="10" skipped="1"/>')
        with self.assertRaises(RuntimeError):M.junit_counts(p)

    def test_empty_suite_rejected(self):
        p=self.root / "tests.xml"
        p.write_text('<testsuite tests="0"/>')
        with self.assertRaises(RuntimeError):M.junit_counts(p)

    def test_suite_failure_rejected(self):
        p=self.root / "tests.xml"
        p.write_text('<testsuite tests="10" failures="1"/>')
        with self.assertRaises(RuntimeError):M.junit_counts(p)

    def test_candidate_identity_and_disjoint_ownership(self):
        owners=set()
        for product,expected in (("theseus","aethel"),("ovid","hyba_db")):
            meta=tomllib.loads((ROOT / f"packaging/{product}/pyproject.toml").read_text())
            self.assertEqual(meta["project"]["version"],"1.0.0")
            include=meta["tool"]["setuptools"]["packages"]["find"]["include"]
            self.assertEqual(include,[expected,expected+".*"])
            self.assertNotIn(expected,owners)
            owners.add(expected)
        self.assertIn("hyba-theseus==1.0.0",meta["project"]["dependencies"])

    def test_no_silent_identity_or_publication_approval(self):
        for product in ("theseus","ovid"):
            row=json.loads((ROOT / f"packaging/{product}/OWNER_DECISIONS.json").read_text())
            self.assertIsNone(row["approved_distribution_name"])
            self.assertIs(row["upload_authorised"],False)
            self.assertIs(row["trusted_publisher_verified"],False)


if __name__=="__main__":unittest.main()

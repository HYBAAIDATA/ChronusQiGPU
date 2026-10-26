"""Production backup methods with real files and explicit actor/event doubles.

Like the PR's run_backup_unit harness, select source methods to avoid loading
unrelated engines. These units do not establish installed custody acceptance.
"""

import ast
import importlib.util
from pathlib import Path
import shutil
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


def load_backup_methods():
    errors_spec = importlib.util.spec_from_file_location(
        "_backup_unit_errors", ROOT / "aethel/enterprise/errors.py",
    )
    errors = importlib.util.module_from_spec(errors_spec)
    errors_spec.loader.exec_module(errors)
    source = ROOT / "aethel/enterprise/custody.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    custody = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "EnterpriseCustody"
    )
    custody.body = [
        node for node in custody.body
        if isinstance(node, ast.FunctionDef) and node.name in {"backup", "_ignore_lock_files"}
    ]
    namespace = {
        "Path": Path, "shutil": shutil, "time": time, "CustodyEvent": SimpleNamespace,
        "AuthorityBoundaryError": errors.AuthorityBoundaryError,
    }
    exec(compile(ast.Module(body=[custody], type_ignores=[]), str(source), "exec"), namespace)
    return namespace["EnterpriseCustody"], errors.AuthorityBoundaryError


BackupMethods, AuthorityBoundaryError = load_backup_methods()


class EnterpriseBackupUnits(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "live" / "tenant"
        self.source.mkdir(parents=True)
        (self.source / "record").write_bytes(b"original")
        self.store = BackupMethods()
        self.store.tenant_root = self.source
        self.store.tenant = "tenant"
        self.store._lock = threading.RLock()
        self.store.telemetry = Mock()
        self.store._append_event = Mock()

    def assert_no_success(self):
        self.store.telemetry.incr.assert_not_called()
        self.store._append_event.assert_not_called()
        self.assertEqual((self.source / "record").read_bytes(), b"original")

    def test_existing_file_and_empty_directory_are_not_overwritten(self):
        existing_file = self.root / "existing-file"
        existing_file.write_bytes(b"precious")
        existing_directory = self.root / "existing-directory"
        existing_directory.mkdir()
        for destination in (existing_file, existing_directory):
            with self.subTest(destination=destination):
                with patch.object(shutil, "copytree") as copy:
                    with self.assertRaises(FileExistsError):
                        self.store.backup(destination)
                    copy.assert_not_called()
                self.assert_no_success()
        self.assertEqual(existing_file.read_bytes(), b"precious")
        self.assertEqual(list(existing_directory.iterdir()), [])

    def test_existing_snapshot_survives_repeated_backup(self):
        destination = self.root / "snapshot"
        self.store.backup(destination)
        self.store.telemetry.reset_mock()
        self.store._append_event.reset_mock()
        (self.source / "new-record").write_bytes(b"new")
        with self.assertRaises(FileExistsError):
            self.store.backup(destination)
        self.assertEqual((destination / "record").read_bytes(), b"original")
        self.assertFalse((destination / "new-record").exists())
        self.assert_no_success()

    def test_overlap_and_parent_traversal_are_refused_before_copy(self):
        for destination in (
            self.source, self.source.parent, self.source.parent.parent,
            self.source / "nested", self.source / "absent" / "..",
        ):
            with self.subTest(destination=destination):
                with patch.object(shutil, "copytree") as copy:
                    with self.assertRaises(AuthorityBoundaryError):
                        self.store.backup(destination)
                    copy.assert_not_called()
                self.assert_no_success()
        self.assertFalse((self.source / "nested").exists())
        self.assertFalse((self.source / "absent").exists())

    def test_existing_symlink_preserves_link_and_target(self):
        target = self.root / "target"
        target.mkdir()
        (target / "precious").write_bytes(b"preserve")
        link = self.root / "link"
        link.symlink_to(target, target_is_directory=True)
        with self.assertRaises(FileExistsError):
            self.store.backup(link)
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.readlink(), target)
        self.assertEqual((target / "precious").read_bytes(), b"preserve")
        self.assert_no_success()

    def test_dangling_symlink_is_preserved_even_when_exists_is_false(self):
        target = self.root / "missing"
        link = self.root / "dangling"
        link.symlink_to(target, target_is_directory=True)
        self.assertFalse(link.exists())
        with patch.object(shutil, "copytree") as copy:
            with self.assertRaises(FileExistsError):
                self.store.backup(link)
            copy.assert_not_called()
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.readlink(), target)
        self.assertFalse(target.exists())
        self.assert_no_success()

    def test_symlink_alias_to_live_root_is_an_overlap(self):
        link = self.root / "alias"
        link.symlink_to(self.source, target_is_directory=True)
        for destination in (link, link / "nested"):
            with self.subTest(destination=destination):
                with patch.object(shutil, "copytree") as copy:
                    with self.assertRaises(AuthorityBoundaryError):
                        self.store.backup(destination)
                    copy.assert_not_called()
                self.assert_no_success()
        self.assertTrue(link.is_symlink())
        self.assertFalse((self.source / "nested").exists())

    def test_sibling_with_same_path_prefix_is_disjoint(self):
        destination = self.source.with_name("tenant-snapshot")
        result = self.store.backup(str(destination))
        self.assertEqual(result, destination)
        self.assertEqual((destination / "record").read_bytes(), b"original")
        self.assertEqual((self.source / "record").read_bytes(), b"original")
        self.store.telemetry.incr.assert_called_once_with("backup_ok")
        self.store._append_event.assert_called_once()
        event = self.store._append_event.call_args.args[0]
        self.assertEqual(
            (event.event_type, event.record_id, event.generation, event.tenant, event.note),
            ("backup", "*", 0, "tenant", str(destination)),
        )

    def test_new_backup_keeps_nested_records_and_excludes_lock_files(self):
        (self.source / "custody.lock").write_bytes(b"locked")
        nested = self.source / "nested"
        nested.mkdir()
        (nested / "writer.lock").write_bytes(b"locked")
        (nested / "record").write_bytes(b"nested")
        destination = self.root / "snapshots" / "first"
        self.store.backup(destination)
        self.assertEqual(
            sorted(path.relative_to(destination).as_posix() for path in destination.rglob("*")),
            ["nested", "nested/record", "record"],
        )
        self.assertEqual((destination / "nested/record").read_bytes(), b"nested")
        self.assertTrue((self.source / "custody.lock").exists())

    def test_failed_copy_preserves_partial_destination_without_success_event(self):
        destination = self.root / "partial"
        failure = OSError("copy interrupted")

        def interrupted_copy(source, target, **kwargs):
            target.mkdir()
            (target / "partial-record").write_bytes(b"partial")
            raise failure

        with patch.object(shutil, "copytree", side_effect=interrupted_copy):
            with self.assertRaises(OSError) as caught:
                self.store.backup(destination)
        self.assertIs(caught.exception, failure)
        self.assertEqual((destination / "partial-record").read_bytes(), b"partial")
        self.assert_no_success()

    def test_destination_created_after_preflight_is_preserved(self):
        destination = self.root / "raced"
        copytree = shutil.copytree

        def racing_copy(source, target, **kwargs):
            target.mkdir()
            (target / "precious").write_bytes(b"another-writer")
            return copytree(source, target, **kwargs)

        with patch.object(shutil, "copytree", side_effect=racing_copy):
            with self.assertRaises(FileExistsError):
                self.store.backup(destination)
        self.assertEqual((destination / "precious").read_bytes(), b"another-writer")
        self.assertFalse((destination / "record").exists())
        self.assert_no_success()


if __name__ == "__main__":
    unittest.main()

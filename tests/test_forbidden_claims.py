import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import pytest

pytestmark = pytest.mark.simulated

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('claims', ROOT/'scripts/ci/check_forbidden_claims.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class ClaimScanTests(unittest.TestCase):
    def test_scans_all_tracked_files_case_insensitively(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            (root/'scripts/ci').mkdir(parents=True)
            (root/'scripts/ci/claim_token_bytes.json').write_text(json.dumps([[66,65,68]]))
            (root/'file.bin').write_bytes(b'good')
            subprocess.run(['git', 'add', '.'], cwd=root, check=True)
            self.assertEqual(check.scan(root), [])
            (root/'file.bin').write_bytes(b'\x00bAd\x00')
            self.assertEqual(check.scan(root), [('file.bin','bad')])

    def test_empty_policy_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'scripts/ci').mkdir(parents=True)
            (root/'scripts/ci/claim_token_bytes.json').write_text('[]')
            with self.assertRaises(ValueError): check.scan(root)


def _repo(files, policy=None):
    d = tempfile.TemporaryDirectory()
    root = Path(d.name)
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    (root/'scripts/ci').mkdir(parents=True)
    (root/'scripts/ci/claim_token_bytes.json').write_text(json.dumps([[66, 65, 68]]))
    if policy is not None:
        (root/'scripts/ci/claim_token_policy.json').write_text(json.dumps(policy))
    for name, data in files.items():
        target = root/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    subprocess.run(['git', 'add', '.'], cwd=root, check=True)
    return d, root


def _entry(path, count, basis='mathematical-term', note='reviewed wording'):
    return {'path': path, 'token': 0, 'count': count, 'basis': basis, 'note': note}


class ClaimPolicyTests(unittest.TestCase):
    def test_allowlisted_occurrence_passes_only_at_the_recorded_count(self):
        d, root = _repo({'doc.md': b'one bad term'}, {'excluded_prefixes': [], 'allowlist': [_entry('doc.md', 1)]})
        with d:
            self.assertEqual(check.scan(root), [])
            (root/'doc.md').write_bytes(b'bad and BAD again')
            self.assertEqual(check.scan(root), [('doc.md', 'bad (found 2, allowlisted 1)')])

    def test_unlisted_file_still_fails(self):
        d, root = _repo({'doc.md': b'bad', 'other.md': b'bad'}, {'excluded_prefixes': [], 'allowlist': [_entry('doc.md', 1)]})
        with d:
            self.assertEqual(check.scan(root), [('other.md', 'bad')])

    def test_stale_entry_fails(self):
        d, root = _repo({'doc.md': b'clean'}, {'excluded_prefixes': [], 'allowlist': [_entry('doc.md', 1)]})
        with d:
            self.assertEqual(check.scan(root), [('doc.md', 'stale allowlist entry for token 0')])

    def test_excluded_prefix_is_not_scanned(self):
        d, root = _repo({'vendor/lib.c': b'bad', 'src/x.py': b'fine'}, {'excluded_prefixes': ['vendor/'], 'allowlist': []})
        with d:
            self.assertEqual(check.scan(root), [])

    def test_excluded_suffix_is_not_scanned(self):
        d, root = _repo({'page.mhtml': b'bad', 'src/x.py': b'fine'}, {'excluded_prefixes': [], 'excluded_suffixes': ['.mhtml'], 'allowlist': []})
        with d:
            self.assertEqual(check.scan(root), [])

    def test_suffix_without_leading_dot_is_rejected(self):
        d, root = _repo({'src/x.py': b'fine'}, {'excluded_prefixes': [], 'excluded_suffixes': ['mhtml'], 'allowlist': []})
        with d:
            with self.assertRaisesRegex(ValueError, 'must start with a dot'):
                check.scan(root)

    def test_excluded_suffix_is_case_insensitive(self):
        d, root = _repo({'page.MHTML': b'bad', 'src/x.py': b'fine'}, {'excluded_prefixes': [], 'excluded_suffixes': ['.mhtml'], 'allowlist': []})
        with d:
            self.assertEqual(check.scan(root), [])

    def test_excluded_suffix_matches_the_final_suffix_only(self):
        # "notes.mhtml.txt" ends in .txt, so it is not a saved page.
        d, root = _repo({'notes.mhtml.txt': b'bad', 'page.mhtml': b'fine'}, {'excluded_prefixes': [], 'excluded_suffixes': ['.mhtml'], 'allowlist': []})
        with d:
            self.assertEqual(check.scan(root), [('notes.mhtml.txt', 'bad')])

    def test_entry_without_recognised_basis_fails_closed(self):
        for bad in (_entry('doc.md', 1, basis='marketing'), _entry('doc.md', 1, note=' '), _entry('doc.md', 0)):
            d, root = _repo({'doc.md': b'bad'}, {'excluded_prefixes': [], 'allowlist': [bad]})
            with d, self.assertRaises(ValueError):
                check.scan(root)

    def test_excluded_prefix_must_be_relative_directory(self):
        d, root = _repo({'doc.md': b'fine'}, {'excluded_prefixes': ['/vendor/'], 'allowlist': []})
        with d, self.assertRaises(ValueError):
            check.scan(root)


if __name__ == '__main__': unittest.main()

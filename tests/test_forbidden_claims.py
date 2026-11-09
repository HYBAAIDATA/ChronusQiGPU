import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

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


if __name__ == '__main__': unittest.main()

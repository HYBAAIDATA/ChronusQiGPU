import importlib.util
import json
import hashlib
from pathlib import Path
import tempfile
import unittest
import pytest

pytestmark = pytest.mark.real

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('verifier', ROOT/'scripts/ci/verify_capacity_artifacts.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


class ArtifactVerifierTests(unittest.TestCase):
    def test_committed_artifact(self):
        self.assertGreater(v.verify(ROOT), 0)

    def test_modified_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'artifacts/capacity'; p.mkdir(parents=True)
            (p/'INDEX.md').write_text('index')
            (p/('a'*64+'.json')).write_text('{}')
            with self.assertRaisesRegex(ValueError, 'content address mismatch'):
                v.verify(Path(d))

    def test_missing_index_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'artifacts/capacity'; p.mkdir(parents=True)
            raw = json.dumps({'sample_hash_sha256':'f', 'source':{'commit':'a'}}).encode()
            (p/(hashlib.sha256(raw).hexdigest()+'.json')).write_bytes(raw)
            (p/'INDEX.md').write_text('index')
            with self.assertRaisesRegex(ValueError, 'missing provenance'):
                v.verify(Path(d))


if __name__ == '__main__': unittest.main()

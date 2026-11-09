import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('capacity', ROOT / 'harness/capacity.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


class HarnessTests(unittest.TestCase):
    def test_roundtrip_and_truthful_unavailable_fields(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p/'data').mkdir()
            (p/'data/a').write_bytes(b'hello')
            (p/'labels.json').write_text(json.dumps({'a': 'text'}))
            (p/'hardware.json').write_text(json.dumps(dict(cpu='test', ram='test', disk='test', gpu='not used')))
            args = SimpleNamespace(data_dir=str(p/'data'), labels=str(p/'labels.json'), hardware=str(p/'hardware.json'),
                                   repetitions=3, export_commit='a'*40, export_codec_blob=h.git_blob(h.CODEC.read_bytes()))
            r = h.run(args, 'test')
            c = r['per_class']['text']
            self.assertIsNone(c['write_amplification'])
            self.assertIsNone(c['recovery_success_rate'])
            self.assertEqual(len(c['decode_latency_ns']['samples']), 3)
            self.assertEqual(r['sample_manifest'][0]['sha256'], h.sha(b'hello'))
            (p/'labels.json').write_text('{}')
            with self.assertRaises(ValueError): h.run(args, 'test')

    def test_percentiles_and_invalid_blob(self):
        self.assertEqual(h.percentile([3, 1, 2], .5), 2)
        with self.assertRaises(ValueError): h.source_identity('a'*40, 'b'*40)


if __name__ == '__main__':
    unittest.main()

class ProbeTests(unittest.TestCase):
    def test_controlled_corruption_is_detected_not_recovered(self):
        codec = h.load_codec()
        source = b'hello'
        payload, header = codec.encode(source)
        probe = h.probe_corruption(codec, payload, header, source)
        self.assertFalse(probe['success'])
        self.assertEqual(probe['outcome'], 'corruption rejected')
        self.assertGreaterEqual(probe['time_to_failure_ns'], 0)
        self.assertNotIn('time_to_success_ns', probe)

    def test_empty_payload_has_no_probe(self):
        codec = h.load_codec()
        payload, header = codec.encode(b'')
        self.assertIsNone(h.probe_corruption(codec, payload, header, b''))

    def test_block_counter_unavailable_is_not_physical_measurement(self):
        with tempfile.TemporaryDirectory() as d:
            result = h.block_write_observation(d, b'abc', b'd', 3)
            self.assertTrue('physical_write_amplification' not in result or result['physical_write_amplification'] is None)

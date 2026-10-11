import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
from chronos.engine import ChronosEngine
from chronos.lucas_runtime import LucasRuntime, ReferenceLucasBackend

class LucasRuntimeTests(unittest.TestCase):
    def test_reference_backend_is_exact_and_measured(self):
        runtime = LucasRuntime(ReferenceLucasBackend())
        self.assertTrue(runtime.capabilities.exact_integer_arithmetic)
        self.assertFalse(runtime.capabilities.hardware_accelerated)
        records = runtime.evaluate([0, 1, 5, 10])
        self.assertEqual([r.index for r in records], [0, 1, 5, 10])
        for record in records: record.verify()

    def test_chronos_render_consumes_lucas_records(self):
        output = ChronosEngine(n_faces=8).render(scene='lucas_runtime_test')
        self.assertEqual(output.lucas_records, 8)
        self.assertEqual(output.lucas_backend, 'python-exact-reference')

if __name__ == '__main__': unittest.main()

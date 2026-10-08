import sys
from dataclasses import replace
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
from chronos.adapters import AdapterRegistry, CpuAdapter, OpenCLAdapter, default_pipeline_spec, BackendAbsent
from chronos.certificate import bind_record, sign_certificate, verify_signature
from chronos.lucas_datapath import DatapathConfig, MiningTarget, SpatialLucasPipeline
from chronos.pool import StratumJob, ShareResponse, bind_response, lucas_to_stratum
from chronos.sparse import lucas_sparse, sparse_dispatch
from chronos.lucas_engine import lucas

class NextRoundTests(unittest.TestCase):
    def test_cpu_adapter_receipt_is_measured_and_named(self):
        adapter = CpuAdapter(DatapathConfig(working_width=32, prime_rom_limit=1000))
        kernel = adapter.compile(default_pipeline_spec(32))
        result = adapter.dispatch(kernel, [0, 1, 10])
        receipt = adapter.receipt()
        self.assertTrue(result.measured)
        self.assertEqual(receipt.backend, 'cpu-exact-reference')
        self.assertTrue(receipt.measured)
        self.assertEqual(len(result.records), 3)

    def test_registry_cpu_only_and_opencl_fail_closed(self):
        reg = AdapterRegistry(); reg.register(CpuAdapter(DatapathConfig(working_width=32, prime_rom_limit=1000)))
        self.assertEqual(reg.select('cpu_only').kind, 'cpu')
        reg.register(OpenCLAdapter())
        try:
            selected = reg.select('prefer_gpu')
            self.assertEqual(selected.kind, 'opencl')
        except BackendAbsent:
            pass

    def test_sparse_agrees_with_exact_and_tier_dispatch(self):
        self.assertEqual([lucas_sparse(n) for n in range(51)], [lucas(n) for n in range(51)])
        result = sparse_dispatch(18, range(32), width=32, prime_rom_limit=1000)
        self.assertEqual(result.execution_mode, 'sparse')
        self.assertEqual(len(result.records), 32)

    def test_certificate_binding_and_hmac(self):
        adapter = CpuAdapter(DatapathConfig(working_width=32, prime_rom_limit=1000))
        kernel = adapter.compile(default_pipeline_spec(32)); result = adapter.dispatch(kernel, [10])
        cert = bind_record(result.records[0], adapter.receipt(), 'sparse')
        signed = sign_certificate(cert, b'test-secret')
        self.assertEqual(signed.classification, 'MEASURED')
        self.assertTrue(verify_signature(signed, b'test-secret'))
        self.assertFalse(verify_signature(signed, b'wrong'))

    def test_offline_pool_conversion_binds_response(self):
        pipeline = SpatialLucasPipeline(DatapathConfig(working_width=32, prime_rom_limit=1000))
        record = pipeline.process_one(10)
        from chronos.lucas_datapath import LucasShare
        share = LucasShare(record, MiningTarget(2**32 - 1))
        sub = lucas_to_stratum(share, StratumJob('job-1', '1234', 4), 'worker-1')
        bound = bind_response(sub, ShareResponse(True, 'response-1'))
        self.assertEqual(bound.certificate_digest, record.certificate)

if __name__ == '__main__': unittest.main()

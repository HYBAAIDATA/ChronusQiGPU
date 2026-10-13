import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
from chronos.igpu import OneIGPU, PrimeDB, HostGPUPlan, MLAObject, lucas
from chronos.igpu.extended_algebra import run_extended_tests

class OneIGPUTests(unittest.TestCase):
    def test_single_facade_modes_share_exact_records(self):
        rungs=list(range(32))
        integrated=OneIGPU('integrated_iGPU', lanes=4, working_width=32, prime_rom_limit=1000).dispatch(rungs)
        overlay=OneIGPU('host_gpu_overlay', lanes=8, working_width=32, prime_rom_limit=1000).dispatch(rungs)
        self.assertEqual([r.value for r in integrated.records], [r.value for r in overlay.records])
        self.assertEqual(integrated.plan['coverage'], 32)
        self.assertEqual(sum(t['end']-t['start'] for t in integrated.plan['tiles']), 32)
    def test_prime_db_is_part_of_one_facade(self):
        with tempfile.TemporaryDirectory() as d:
            gpu=OneIGPU('cpu_reference', working_width=32, prime_rom_limit=1000, db_path=Path(d)/'prime.db')
            obj=gpu.put({'value':lucas(15)}, sequence_index=15, scale=15)
            self.assertTrue(gpu.db.verify(obj.object_id)['valid'])
            self.assertEqual(gpu.db.count(), 1)
            gpu.close()
    def test_reference_algebra_suite(self):
        result=run_extended_tests()
        self.assertTrue(all(t['status']=='PASS' for t in result['tests']))
        self.assertTrue(any(h['status']=='REFUTED' for h in result['hypotheses']))
    def test_object_tamper_fails(self):
        obj=MLAObject.create({'x':1}, 15)
        data=obj.to_dict(); data['lucas_scale'] += 1
        from dataclasses import replace
        tampered=replace(obj, lucas_scale=obj.lucas_scale+1)
        with self.assertRaises(ValueError): tampered.validate()

if __name__=='__main__': unittest.main()

import unittest,platform,numpy as np
from chronos import OneIGPU
from chronos.igpu import LinearNeuralRanker,MLXOverlay,CoreMLRanker
from chronos.adapters.base import BackendAbsent
class AppleExtensionTests(unittest.TestCase):
    def test_ranker_preserves_candidates(self):
        ranker=LinearNeuralRanker([[1.]], [0.]);g=OneIGPU();self.assertEqual(g.neural_rank([10,20,30],[[1.],[3.],[2.]],ranker),(20,30,10))
    def test_ties_stable(self):
        ranker=LinearNeuralRanker([[0.]], [0.]);self.assertEqual(ranker.rank([3,1,2],[[1.],[2.],[3.]]),(3,1,2))
    def test_finiteness_rejected(self):
        with self.assertRaises(ValueError):LinearNeuralRanker([[float('nan')]], [0.])
    def test_feature_shape_rejected(self):
        with self.assertRaises(ValueError):LinearNeuralRanker([[1.]], [0.]).score([[1.,2.]])
    def test_bias_shape_rejected(self):
        with self.assertRaises(ValueError):LinearNeuralRanker([[1.]], [0.,1.])
    def test_duplicate_domain_rejected(self):
        with self.assertRaises(ValueError):LinearNeuralRanker([[1.]], [0.]).rank([1,1],[[1.],[2.]])
    def test_family_facade(self):
        g=OneIGPU();c=g.family_certificate([10,12,15]);self.assertEqual(c['combined_index'],37);self.assertEqual(g.golden.events[-1]['operation'],'family_compose')
    def test_unavailable_apple_bindings(self):
        if platform.system()!='Darwin':
            with self.assertRaises(BackendAbsent):MLXOverlay()
            with self.assertRaises(BackendAbsent):CoreMLRanker('model.mlmodel','x','y')
    def test_tensor_only_adapter_leaves_exact_core_routed_native(self):
        class TensorOnly:
            last_receipt=None
            def capability(self):return {'device_id':'test_tensor','backend':'test_tensor','physical':False,'operations':['tensor']}
            def execute_tensor(self,op,a,b):return np.asarray(a)+np.asarray(b)
        g=OneIGPU(host_adapter=TensorOnly(),working_width=32,prime_rom_limit=1000)
        self.assertEqual(g.route('lucas').executor,'cpu_reference');self.assertTrue(g.dispatch([15]).verify());self.assertEqual(g.tensor('add',[1.],[2.]).tolist(),[3.]);self.assertEqual(g.golden.events[-1]['backend'],'test_tensor')
    def test_ranking_ownership_violation(self):
        class Bad:
            last_receipt={}
            def rank(self,v,f):return [999]
        with self.assertRaises(ValueError):OneIGPU().neural_rank([1],[[0.]],Bad())
if __name__=='__main__':unittest.main()

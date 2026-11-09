"""Test doubles are deliberately deterministic and detached from input state."""
import unittest
from hyba.unification.testing.doubles import StubDomain, StubInvariants, StubNetwork

class TestDoubles(unittest.TestCase):
    def test_network_returns_fixed_result_invariants_and_controlled_ledger(self):
        result, inv, ledger = [3], {'a': [4]}, [{'cut': 1}]
        n = StubNetwork(result, inv, ledger)
        result.append(0); inv['a'].append(0); ledger.clear()
        payload = {'x': [1]}; out = n.contract(payload); payload['x'].append(9)
        self.assertEqual(n.calls, [{'x':[1]}])
        self.assertEqual(out, {'result':[3], 'invariants':{'a':[4]}, 'ledger':[{'cut':1}]})
        out['ledger'].clear(); self.assertEqual(n.contract('other')['ledger'], [{'cut':1}])

    def test_domain_returns_fixed_encoding(self):
        d=StubDomain([1,2]); v={'raw':[3]}; e=d.encode(v); v['raw'].append(4); e.append(8)
        self.assertEqual(d.calls, [{'raw':[3]}]); self.assertEqual(d.encode(None), [1,2])

    def test_invariant_registry_returns_fixed_values(self):
        s=StubInvariants({'fixed':[7]}); out=s.evaluate([1]); out['fixed'].append(8)
        self.assertEqual(s.evaluate([2]), {'fixed':[7]}); self.assertEqual(s.calls, [[1],[2]])

if __name__ == '__main__': unittest.main()

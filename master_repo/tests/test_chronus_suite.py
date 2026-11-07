import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from tests.test_invariants_all import TestAllInvariantsSuite
from tests.test_ns_dec import TestNavierStokesDECSuite
from tests.test_crypto_stark import TestCryptoAndStarkSuite
from tests.test_sdk_api import TestSDKAndAPISuite
from tests.test_hermiten_pricing import TestHermitenAndPricingSuite

def suite():
    s = unittest.TestSuite()
    s.addTest(unittest.makeSuite(TestAllInvariantsSuite))
    s.addTest(unittest.makeSuite(TestNavierStokesDECSuite))
    s.addTest(unittest.makeSuite(TestCryptoAndStarkSuite))
    s.addTest(unittest.makeSuite(TestSDKAndAPISuite))
    s.addTest(unittest.makeSuite(TestHermitenAndPricingSuite))
    return s

if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite())

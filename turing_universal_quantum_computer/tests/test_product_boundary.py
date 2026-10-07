"""TURING is the virtual quantum computer and nothing else.

The hashrate capacity surface and the mining execution plane are Mining's;
copies of TOE, Intelligence and Mining modules were removed in favour of their
owners; tensor mathematics is Kellogg's and is consumed, not forked.
"""

import importlib
import unittest

import turing_universal_quantum_computer as tqc

CARVED_OUT = (
    "fault_tolerant_asic",
    "deterministic_hashrate",
    "thermodynamics_exact",
    "scaled_execution",
    "four_layer_stack",
    "bitcoin_hasher",
    "hash_pipeline",
    "search",
    "turing_adapter",
    "toe_system",
    "hardened_unified_substrate",
    "manifold_bridge",
    "unified_punch",
    "backend_binding",
    "duality",
    "kk_spectrum",
    "extended_algebra",
    "rings",
    "strict_quantum",
    "intelligences",
)


class ProductBoundaryTests(unittest.TestCase):
    def test_carved_out_modules_are_gone(self):
        for name in CARVED_OUT:
            with self.subTest(module=name):
                with self.assertRaises(ImportError):
                    importlib.import_module(f"turing_universal_quantum_computer.{name}")

    def test_capacity_surface_is_not_exported(self):
        for name in ("PureQuantumMathASIC", "DeterministicMiningSystem", "LucasScaledAethelExecutionAdapter",
                     "FourLayerMiningStack", "certify_work_window", "TuringMiningSubstrate"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(tqc, name))
        system = tqc.TenThousandQubitSystem(n_qubits=32)
        for accessor in ("pure_quantum_asic", "deterministic_10eh_system", "heterogeneous_10eh_certificate"):
            self.assertFalse(hasattr(system, accessor))
        status = system.status()
        self.assertNotIn("deterministic_10eh_capacity_certificate", status["capabilities"])
        self.assertIn("mps_exact", status["backends"])

    def test_tensor_mathematics_is_kelloggs(self):
        import kellogg.exact_tensor
        import kellogg.quantum_tensor
        from turing_universal_quantum_computer import exact_tensor, quantum_tensor

        self.assertIs(exact_tensor, kellogg.exact_tensor)
        self.assertIs(quantum_tensor, kellogg.quantum_tensor)

    def test_manifest_custody_keeps_working(self):
        system = tqc.TenThousandQubitSystem(n_qubits=16)
        record = system.custody_manifest()
        self.assertIn("address", record)
        self.assertEqual(record, {**record, "address": "ten_thousand:manifest"})


if __name__ == "__main__":
    unittest.main()

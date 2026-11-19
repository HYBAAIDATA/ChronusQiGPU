# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Fleet kernels: pinned known answers re-derived independently, route parity, tiling."""

import hashlib
import json
import unittest

from chronus.fleet import kernels as K
from chronus.fleet.canonical import deterministic_bytes
from chronus.fleet.errors import KernelError
import pytest

pytestmark = pytest.mark.real

MANIFESTO_M15 = (219, 98, 98, 121)
MANIFESTO_M15_INV = (135, 98, 98, 37)


def fold_pairs(data, matrix):
    a, b, c, d = matrix
    out = bytearray()
    for i in range(0, len(data), 2):
        x, y = data[i], data[i + 1]
        out += bytes(((a * x + b * y) % 256, (c * x + d * y) % 256))
    return bytes(out)


def fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def run_whole(kernel, params, payload, route="reference"):
    prepared = kernel.prepare(params, payload)
    tile = kernel.tile_input(prepared, 0, prepared.items)
    return kernel.implementation(route)(None, prepared.params, tile, 0, prepared.items)


def run_tiled(kernel, params, payload, cuts, route="reference"):
    prepared = kernel.prepare(params, payload)
    bounds = [0] + [c for c in cuts if 0 < c < prepared.items] + [prepared.items]
    outputs = []
    for start, stop in zip(bounds, bounds[1:]):
        tile = kernel.tile_input(prepared, start, stop)
        outputs.append(kernel.implementation(route)(None, prepared.params, tile, start, stop))
    return kernel.merge(prepared.params, outputs)


class M15Tests(unittest.TestCase):
    def test_matrix_matches_manifesto_and_native_simd(self):
        fold, unfold = K.m15_matrices()
        self.assertEqual(fold, MANIFESTO_M15)
        self.assertEqual(unfold, MANIFESTO_M15_INV)
        self.assertEqual((219 * 121 - 98 * 98) % 256, 255)

    def test_known_answers_rederived(self):
        for kernel, matrix in ((K.M15FoldKernel(), MANIFESTO_M15), (K.M15UnfoldKernel(), MANIFESTO_M15_INV)):
            for answer in kernel.known_answers():
                expected = hashlib.sha256(fold_pairs(answer.payload, matrix)).hexdigest()
                self.assertEqual(answer.output_sha256, expected, f"{kernel.name}/{answer.label}")

    def test_fold_then_unfold_is_identity(self):
        data = deterministic_bytes("roundtrip", 4096)
        folded = run_whole(K.M15FoldKernel(), {}, data)
        self.assertNotEqual(folded, data)
        self.assertEqual(run_whole(K.M15UnfoldKernel(), {}, folded), data)

    def test_simd_matches_reference_and_tiling_is_invisible(self):
        data = deterministic_bytes("parity", 20_002)
        kernel = K.M15FoldKernel()
        reference = run_whole(kernel, {}, data)
        self.assertEqual(run_whole(kernel, {}, data, "simd"), reference)
        self.assertEqual(run_tiled(kernel, {}, data, [1, 7, 4000, 9999], "simd"), reference)

    def test_rejects_odd_or_empty_payload_and_unknown_params(self):
        kernel = K.M15FoldKernel()
        for payload in (b"", b"\x01", b"\x01\x02\x03"):
            with self.assertRaises(KernelError):
                kernel.prepare({}, payload)
        with self.assertRaises(KernelError):
            kernel.prepare({"x": 1}, b"\x01\x02")


class DualSpaceTests(unittest.TestCase):
    def test_known_answers_rederived_through_unfold(self):
        kernel = K.DualSpaceQueryKernel()
        for answer in kernel.known_answers():
            half = len(answer.payload) // 2
            q, y = answer.payload[:half], answer.payload[half:]
            x = fold_pairs(y, MANIFESTO_M15_INV)
            value = sum(a * b for a, b in zip(q, x)) % 256
            self.assertEqual(answer.output_sha256, hashlib.sha256(bytes([value])).hexdigest(), answer.label)

    def test_query_on_folded_data_equals_plain_inner_product(self):
        x = deterministic_bytes("dual-x", 2048)
        q = deterministic_bytes("dual-q", 2048)
        y = fold_pairs(x, MANIFESTO_M15)
        expected = sum(a * b for a, b in zip(q, x)) % 256
        kernel = K.DualSpaceQueryKernel()
        self.assertEqual(run_whole(kernel, {}, q + y), bytes([expected]))
        self.assertEqual(run_whole(kernel, {}, q + y, "simd"), bytes([expected]))
        self.assertEqual(run_tiled(kernel, {}, q + y, [3, 100, 511]), bytes([expected]))


class GFMatVecTests(unittest.TestCase):
    def naive(self, p, rows, cols, payload):
        words = [int.from_bytes(payload[i : i + 4], "little") for i in range(0, len(payload), 4)]
        a, x = words[: rows * cols], words[rows * cols :]
        y = [sum(a[r * cols + c] * x[c] for c in range(cols)) % p for r in range(rows)]
        return b"".join(v.to_bytes(4, "little") for v in y)

    def test_known_answers_rederived_with_plain_modular_arithmetic(self):
        kernel = K.GFMatVecKernel()
        for answer in kernel.known_answers():
            p, rows, cols = (answer.params[k] for k in ("p", "rows", "cols"))
            expected = hashlib.sha256(self.naive(p, rows, cols, answer.payload)).hexdigest()
            self.assertEqual(answer.output_sha256, expected, answer.label)

    def test_simd_and_tiles_match_reference(self):
        kernel = K.GFMatVecKernel()
        params, payload = kernel.benchmark()
        reference = run_whole(kernel, params, payload)
        self.assertEqual(reference, self.naive(params["p"], params["rows"], params["cols"], payload))
        self.assertEqual(run_whole(kernel, params, payload, "simd"), reference)
        self.assertEqual(run_tiled(kernel, params, payload, [5, 50]), reference)

    def test_rejects_non_prime_large_field_and_unreduced_entries(self):
        kernel = K.GFMatVecKernel()
        payload = (1).to_bytes(4, "little") * 2
        with self.assertRaises(KernelError):
            kernel.prepare({"p": 1 << 21, "rows": 1, "cols": 1}, payload)
        with self.assertRaises((KernelError, ValueError)):
            kernel.prepare({"p": 15, "rows": 1, "cols": 1}, payload)
        with self.assertRaises(KernelError):
            kernel.prepare({"p": 7, "rows": 1, "cols": 1}, (9).to_bytes(4, "little") * 2)


class PVLatticeTests(unittest.TestCase):
    def expected(self, values, order):
        c, d = fibonacci(order - 1) if order else 1, fibonacci(order)
        out = []
        for v in values:
            a, b = int(v["a"]), int(v["b"])
            out.append({"a": str(a * c + b * d), "b": str(a * d + b * c + b * d), "denominator": str(int(v["denominator"]))})
        return json.dumps(out, separators=(",", ":"), sort_keys=True).encode()

    def test_known_answers_rederived_from_fibonacci(self):
        kernel = K.PVLatticeFoldKernel()
        for answer in kernel.known_answers():
            values = json.loads(answer.payload)
            digest = hashlib.sha256(self.expected(values, answer.params["order"])).hexdigest()
            self.assertEqual(answer.output_sha256, digest, answer.label)

    def test_lucas_90_matches_the_opencl_backend_known_answer(self):
        out = json.loads(run_whole(K.PVLatticeFoldKernel(), {"order": 90}, b'[{"a":1,"b":0,"denominator":1}]'))
        a, b = int(out[0]["a"]), int(out[0]["b"])
        self.assertEqual(2 * a + b, 6440026026380244498)
        self.assertEqual(b, 2880067194370816120)

    def test_simd_declines_int64_overflow_instead_of_wrapping(self):
        kernel = K.PVLatticeFoldKernel()
        payload = json.dumps([{"a": str((1 << 62) - 1), "b": "3", "denominator": "1"}]).encode()
        prepared = kernel.prepare({"order": 80}, payload)
        tile = kernel.tile_input(prepared, 0, 1)
        self.assertIsNotNone(kernel.accepts("simd", None, prepared.params, tile, 0, 1))
        self.assertIsNone(kernel.accepts("reference", None, prepared.params, tile, 0, 1))

    def test_simd_and_tiles_match_reference(self):
        kernel = K.PVLatticeFoldKernel()
        params, payload = kernel.benchmark()
        reference = run_whole(kernel, params, payload)
        self.assertEqual(run_whole(kernel, params, payload, "simd"), reference)
        self.assertEqual(run_tiled(kernel, params, payload, [1, 100, 511]), reference)


class RegistryTests(unittest.TestCase):
    def test_builtins_and_plugins(self):
        registry = K.default_registry(plugins=["tests.fleet_test_kernels"])
        self.assertIn("m15_fold", registry)
        self.assertIn("m15_fold_paced", registry)
        plugin = registry.get("m15_fold_paced")
        answer = plugin.known_answers()[0]
        self.assertEqual(hashlib.sha256(plugin.reference_output(answer.params, answer.payload)).hexdigest(), answer.output_sha256)
        with self.assertRaises(KernelError):
            registry.get("m15_fold", version="99")
        with self.assertRaises(KernelError):
            registry.get("no_such_kernel")

    def test_duplicate_and_reference_free_kernels_are_refused(self):
        registry = K.KernelRegistry([K.M15FoldKernel()])
        with self.assertRaises(KernelError):
            registry.register(K.M15FoldKernel())

        class NoReference(K.Kernel):
            name = "broken"

            def implementation(self, route):
                return None

        with self.assertRaises(KernelError):
            registry.register(NoReference())

    def test_every_builtin_has_known_answers_and_a_reference(self):
        for kernel in K.default_registry(plugins=[]):
            self.assertTrue(kernel.known_answers(), kernel.name)
            self.assertIn("reference", kernel.routes())


if __name__ == "__main__":
    unittest.main()

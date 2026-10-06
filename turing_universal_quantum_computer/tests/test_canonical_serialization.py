import unittest
from dataclasses import dataclass
from fractions import Fraction

from turing_universal_quantum_computer.canonical_serialization import (
    CanonicalSerializationError,
    canonical_serialize,
    canonical_sha256,
)


class CanonicalSerializationTests(unittest.TestCase):
    def test_object_order_does_not_change_bytes_or_digest(self):
        left = {"z": 2, "a": Fraction(2, 4)}
        right = {"a": Fraction(1, 2), "z": 2}
        self.assertEqual(canonical_serialize(left), canonical_serialize(right))
        self.assertEqual(canonical_sha256(left), canonical_sha256(right))

    def test_exact_types_have_published_encodings(self):
        self.assertEqual(
            canonical_serialize({"q": Fraction(-2, 6), "b": b"\x00\xff"}),
            b'{"b":{"$bytes_hex":"00ff"},"q":{"$rational":'
            b'{"denominator":3,"numerator":-1}}}',
        )

    def test_dataclasses_and_tuples_are_normalized(self):
        @dataclass(frozen=True)
        class Row:
            value: Fraction

        self.assertEqual(
            canonical_serialize((Row(Fraction(3, 2)),)),
            b'[{"value":{"$rational":{"denominator":2,"numerator":3}}}]',
        )

    def test_float_non_string_key_and_unknown_type_fail_closed(self):
        for value in (1.0, {"x": 1.0}, {1: "x"}, object()):
            with self.subTest(value=repr(value)):
                with self.assertRaises(CanonicalSerializationError):
                    canonical_serialize(value)


if __name__ == "__main__":
    unittest.main()
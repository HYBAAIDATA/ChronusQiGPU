"""Procurement reserve/admit fail-closed behaviour and OpenAPI seal."""

from __future__ import annotations

import unittest

from chronus.core.seal import seal_schema
from chronus.procurement.book import Book, Refusal, admit, reserve
from chronus.procurement.quote import CONTRACT_VERSION, build_quote, live_evidence_hash
from chronus.service.api.routers.procurement import openapi_fragment


class ProcurementBookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evidence = live_evidence_hash()
        self.quote = build_quote(
            1_000,
            tier="TIER_POLYNOMIAL",
            contract_version=CONTRACT_VERSION,
            evidence_hash=self.evidence,
        )
        self.book = Book(pool_bytes=50_000_000, ttl_s=60.0, pool_source="test")

    def test_idempotent_reserve_and_refusals(self) -> None:
        res = reserve(
            self.book,
            CONTRACT_VERSION,
            self.evidence,
            self.quote,
            "key-1",
            now=1_000.0,
        )
        again = reserve(
            self.book,
            CONTRACT_VERSION,
            self.evidence,
            self.quote,
            "key-1",
            now=1_000.0,
        )
        self.assertEqual(res.id, again.id)

        cases = (
            ({**self.quote, "releases_old": 1}, "stale_envelope"),
            ({**self.quote, "contract_version": "old"}, "version_mismatch"),
            ({**self.quote, "evidence_hash": "f" * 64}, "evidence_mismatch"),
            ({**self.quote, "is_binding": False}, "quote_not_binding"),
        )
        for bad, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(Refusal) as ctx:
                    reserve(
                        self.book,
                        CONTRACT_VERSION,
                        self.evidence,
                        bad,
                        f"k-{code}",
                        now=1_000.0,
                    )
                self.assertEqual(ctx.exception.code, code)

    def test_admit_overage_and_double_consume(self) -> None:
        res = reserve(
            self.book,
            CONTRACT_VERSION,
            self.evidence,
            self.quote,
            "key-admit",
            now=1_000.0,
        )
        out = admit(self.book, res.id, 1_010, now=1_001.0)
        self.assertEqual(out["utilisation"], 1.01)
        with self.assertRaises(Refusal) as ctx:
            admit(self.book, res.id, 1_010, now=1_002.0)
        self.assertEqual(ctx.exception.code, "already_consumed")

        res2 = reserve(
            self.book,
            CONTRACT_VERSION,
            self.evidence,
            self.quote,
            "key-over",
            now=1_000.0,
        )
        with self.assertRaises(Refusal) as ctx:
            admit(self.book, res2.id, 12_000, now=1_001.0)
        self.assertEqual(ctx.exception.code, "overage")

    def test_pool_exhausted(self) -> None:
        tiny = Book(pool_bytes=4_000, ttl_s=60.0, pool_source="test")
        with self.assertRaises(Refusal) as ctx:
            reserve(
                tiny,
                CONTRACT_VERSION,
                self.evidence,
                self.quote,
                "k-pool",
                now=1_000.0,
            )
        self.assertEqual(ctx.exception.code, "pool_exhausted")

    def test_openapi_fragment_is_sealed(self) -> None:
        fragment = openapi_fragment()
        seal_schema(fragment)
        with self.assertRaises(AssertionError):
            seal_schema({"/v1/fibonacci": {}})


if __name__ == "__main__":
    unittest.main()

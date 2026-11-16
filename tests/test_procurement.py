"""Procurement reserve/admit fail-closed behaviour and OpenAPI seal."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from chronus.core.seal import seal_schema
from chronus.procurement.book import Book, Refusal, admit, reserve
from chronus.procurement.ledger import UtilisationLedger
from chronus.procurement.quote import CONTRACT_VERSION, build_quote, live_evidence_hash
from chronus.service.api.routers.procurement import (
    CAPACITY_OPENAPI_PATHS,
    capacity_openapi_fragment,
    openapi_fragment,
)

TENANT = "tenant-a"
OTHER = "tenant-b"


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
            tenant_id=TENANT,
            now=1_000.0,
        )
        again = reserve(
            self.book,
            CONTRACT_VERSION,
            self.evidence,
            self.quote,
            "key-1",
            tenant_id=TENANT,
            now=1_000.0,
        )
        self.assertEqual(res.id, again.id)
        other_quote = build_quote(
            2_000,
            tier="TIER_POLYNOMIAL",
            contract_version=CONTRACT_VERSION,
            evidence_hash=self.evidence,
        )
        with self.assertRaises(Refusal) as conflict:
            reserve(
                self.book,
                CONTRACT_VERSION,
                self.evidence,
                other_quote,
                "key-1",
                tenant_id=TENANT,
                now=1_000.0,
            )
        self.assertEqual(conflict.exception.code, "idempotency_conflict")

        # Server rebuilds the quote: tampered economics → invalid_quote;
        # releases_old ≠ 0 → stale_envelope.
        cases = (
            ({**self.quote, "releases_old": 1}, "stale_envelope"),
            ({**self.quote, "contract_version": "old"}, "invalid_quote"),
            ({**self.quote, "evidence_hash": "f" * 64}, "invalid_quote"),
            ({**self.quote, "is_binding": False}, "invalid_quote"),
            ({**self.quote, "space_bytes": 1}, "invalid_quote"),
        )
        for bad, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(Refusal) as ctx:
                    reserve(
                        self.book,
                        CONTRACT_VERSION,
                        self.evidence,
                        bad,
                        f"k-{code}-{bad.get('space_bytes', 0)}",
                        tenant_id=TENANT,
                        now=1_000.0,
                    )
                self.assertEqual(ctx.exception.code, code)

    def test_tenant_isolation_on_idempotency_and_admit(self) -> None:
        res_a = reserve(
            self.book,
            CONTRACT_VERSION,
            self.evidence,
            self.quote,
            "shared-key",
            tenant_id=TENANT,
            now=1_000.0,
        )
        res_b = reserve(
            self.book,
            CONTRACT_VERSION,
            self.evidence,
            self.quote,
            "shared-key",
            tenant_id=OTHER,
            now=1_000.0,
        )
        self.assertNotEqual(res_a.id, res_b.id)

        with self.assertRaises(Refusal) as ctx:
            admit(self.book, res_a.id, 1_000, tenant_id=OTHER, now=1_001.0)
        self.assertEqual(ctx.exception.code, "unknown_reservation")

        out = admit(self.book, res_a.id, 1_000, tenant_id=TENANT, now=1_001.0)
        self.assertEqual(out["tenant_id"], TENANT)
        self.assertEqual(out["utilised_bytes"], res_a.space_bytes)

    def test_admit_idempotent_then_overage(self) -> None:
        res = reserve(
            self.book,
            CONTRACT_VERSION,
            self.evidence,
            self.quote,
            "key-admit",
            tenant_id=TENANT,
            now=1_000.0,
        )
        out = admit(self.book, res.id, 1_010, tenant_id=TENANT, now=1_001.0)
        self.assertEqual(out["utilisation"], 1.01)
        # Retry after ledger hiccup returns the same admission.
        again = admit(self.book, res.id, 1_010, tenant_id=TENANT, now=1_002.0)
        self.assertEqual(again, out)

        res2 = reserve(
            self.book,
            CONTRACT_VERSION,
            self.evidence,
            self.quote,
            "key-over",
            tenant_id=TENANT,
            now=1_000.0,
        )
        with self.assertRaises(Refusal) as ctx:
            admit(self.book, res2.id, 12_000, tenant_id=TENANT, now=1_001.0)
        self.assertEqual(ctx.exception.code, "overage")

    def test_expired_refusal(self) -> None:
        res = reserve(
            self.book,
            CONTRACT_VERSION,
            self.evidence,
            self.quote,
            "key-exp",
            tenant_id=TENANT,
            now=1_000.0,
        )
        with self.assertRaises(Refusal) as ctx:
            admit(self.book, res.id, 1_000, tenant_id=TENANT, now=1_000.0 + 61.0)
        self.assertEqual(ctx.exception.code, "expired")

    def test_pool_exhausted(self) -> None:
        tiny = Book(pool_bytes=4_000, ttl_s=60.0, pool_source="test")
        with self.assertRaises(Refusal) as ctx:
            reserve(
                tiny,
                CONTRACT_VERSION,
                self.evidence,
                self.quote,
                "k-pool",
                tenant_id=TENANT,
                now=1_000.0,
            )
        self.assertEqual(ctx.exception.code, "pool_exhausted")

    def test_ledger_tenant_quarterly_line(self) -> None:
        ledger = UtilisationLedger()
        admission = {
            "reservation": "r1",
            "tier": "TIER_POLYNOMIAL",
            "reserved": 1000,
            "actual": 1000,
            "space_bytes": 8_000_000,
            "utilised_bytes": 8_000_000,
            "utilisation": 1.0,
            "tenant_id": TENANT,
        }
        first = ledger.record(admission, tenant_id=TENANT)
        again = ledger.record(admission, tenant_id=TENANT)
        self.assertIs(first, again)
        self.assertEqual(len(ledger.rows()), 1)
        other = {**admission, "reservation": "r2", "tenant_id": OTHER}
        ledger.record(other, tenant_id=OTHER)

        line = ledger.quarterly_line(
            tenant_id=TENANT,
            baseline_accelerator_hours=10.0,
            since=0.0,
            until=1e18,
        )
        self.assertTrue(line["fee_applicable"])
        self.assertEqual(line["utilised_space_bytes"], 8_000_000)
        self.assertEqual(line["tenant_id"], TENANT)

        none = ledger.quarterly_line(
            tenant_id=TENANT,
            baseline_accelerator_hours=None,
            since=0.0,
            until=1e18,
        )
        self.assertFalse(none["fee_applicable"])

    def test_openapi_fragment_is_sealed_from_live_app(self) -> None:
        from chronus.service.api import security as api_security

        self.addCleanup(api_security.reset_token_cache)
        tokens = patch.dict(
            os.environ,
            {
                "CHRONUS_TENANT_TOKENS": json.dumps(
                    {
                        "seal-test-token": {
                            "tenant_id": "seal",
                            "scopes": ["workloads:read", "workloads:write"],
                        }
                    }
                )
            },
        )
        tokens.start()
        self.addCleanup(tokens.stop)
        api_security.reset_token_cache()
        fragment = openapi_fragment()
        for path in CAPACITY_OPENAPI_PATHS:
            self.assertIn(path, fragment)
        # Same fragment must come from a live schema extraction.
        from chronus.service.api.app import create_app

        again = capacity_openapi_fragment(create_app().openapi())
        self.assertEqual(set(fragment), set(again))
        seal_schema(fragment)
        with self.assertRaises(AssertionError):
            seal_schema({"/v1/fibonacci": {}})
        # Referenced capacity models are sealed too (not only path keys).
        with self.assertRaises(AssertionError):
            capacity_openapi_fragment(
                {
                    "paths": {
                        path: {"post": {"requestBody": {"$ref": "#/components/schemas/Bad"}}}
                        for path in CAPACITY_OPENAPI_PATHS
                    },
                    "components": {
                        "schemas": {
                            "Bad": {
                                "type": "object",
                                "properties": {"phi": {"type": "string"}},
                            }
                        }
                    },
                }
            )
        # Reusable response/requestBody refs must also pull nested schemas.
        with self.assertRaises(AssertionError):
            capacity_openapi_fragment(
                {
                    "paths": {
                        path: {
                            "post": {
                                "responses": {
                                    "200": {"$ref": "#/components/responses/Tainted"}
                                }
                            }
                        }
                        for path in CAPACITY_OPENAPI_PATHS
                    },
                    "components": {
                        "responses": {
                            "Tainted": {
                                "description": "ok",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "$ref": "#/components/schemas/TaintedBody"
                                        }
                                    }
                                },
                            }
                        },
                        "schemas": {
                            "TaintedBody": {
                                "type": "object",
                                "properties": {"fibonacci": {"type": "integer"}},
                            }
                        },
                    },
                }
            )


if __name__ == "__main__":
    unittest.main()

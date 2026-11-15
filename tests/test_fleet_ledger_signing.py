# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""P10 anchor ledger, ML-DSA-65 signing with the existing signer, and receipt verification."""

import json
import unittest
from pathlib import Path

from chronus.fleet.canonical import sha256_hex
from chronus.fleet.errors import LedgerError, SignerUnavailableError
from chronus.fleet.ledger import AnchorLedger, verify_ledger
from chronus.fleet.receipts import RECEIPT_SCHEMA, sign_receipt, verify_receipt
from chronus.fleet.signing import FleetSigner, load_mldsa_signer, verify_signature
from tests.fleet_support import filesystem_keeps_modes, state_dir


def fill(ledger, count):
    return [ledger.append("note", sha256_hex(str(i).encode()), {"i": i}) for i in range(count)]


class LedgerTests(unittest.TestCase):
    def test_append_and_verify(self):
        with state_dir() as tmp:
            ledger = AnchorLedger(Path(tmp) / "ledger.jsonl")
            entries = fill(ledger, 5)
            self.assertEqual([e["seq"] for e in entries], list(range(5)))
            self.assertEqual(entries[0]["prev_hash"], "0" * 64)
            self.assertEqual(entries[3]["prev_hash"], entries[2]["entry_hash"])
            check = verify_ledger(ledger.path)
            self.assertTrue(check.valid)
            self.assertEqual((check.entries, check.head_hash), (5, entries[-1]["entry_hash"]))
            reopened = AnchorLedger(ledger.path)
            self.assertEqual(reopened.head, (5, entries[-1]["entry_hash"]))
            self.assertEqual(reopened.find(entries[2]["digest"])["seq"], 2)

    def test_every_kind_of_tampering_is_detected(self):
        def tampered(edit):
            with state_dir() as tmp:
                ledger = AnchorLedger(Path(tmp) / "ledger.jsonl")
                fill(ledger, 4)
                lines = ledger.path.read_text().splitlines(keepends=True)
                ledger.path.write_text("".join(edit(lines)))
                return verify_ledger(ledger.path)

        def change_digest(lines):
            entry = json.loads(lines[1])
            entry["digest"] = "f" * 64
            return [lines[0], json.dumps(entry) + "\n"] + lines[2:]

        for edit in (
            change_digest,
            lambda lines: lines[:1] + lines[2:],
            lambda lines: [lines[1], lines[0]] + lines[2:],
            lambda lines: lines[:-1] + [lines[-1].rstrip("\n")],
        ):
            check = tampered(edit)
            self.assertFalse(check.valid)
            self.assertIsNotNone(check.reason)

    def test_a_broken_ledger_refuses_new_appends(self):
        with state_dir() as tmp:
            path = Path(tmp) / "ledger.jsonl"
            fill(AnchorLedger(path), 2)
            path.write_text(path.read_text().replace('"seq":1', '"seq":7'))
            with self.assertRaises(LedgerError):
                AnchorLedger(path)

    def test_bad_digest_or_kind_is_refused(self):
        with state_dir() as tmp:
            ledger = AnchorLedger(Path(tmp) / "ledger.jsonl")
            with self.assertRaises(LedgerError):
                ledger.append("note", "abc")
            with self.assertRaises(LedgerError):
                ledger.append("gossip", "0" * 64)


class SigningTests(unittest.TestCase):
    def test_the_signer_is_the_fips_204_v36_signer(self):
        signer_class = load_mldsa_signer()
        self.assertEqual(signer_class.PREFIX, "mldsa65_")
        self.assertTrue(hasattr(signer_class, "tenant_private_key"))

    def test_sign_verify_and_key_persistence(self):
        with state_dir() as tmp:
            signer = FleetSigner.from_state_dir(tmp)
            self.assertEqual(len(signer.public_key), 1952)
            signature = signer.sign(b"chronus fleet")
            self.assertTrue(signature.startswith("mldsa65_"))
            self.assertTrue(verify_signature(signer.public_key, b"chronus fleet", signature))
            self.assertFalse(verify_signature(signer.public_key, b"chronus fleet!", signature))
            self.assertEqual(FleetSigner.from_state_dir(tmp).key_id, signer.key_id)
            seed = Path(tmp) / "coordinator_mldsa65.seed"
            if filesystem_keeps_modes(tmp):
                self.assertEqual(seed.stat().st_mode & 0o777, 0o600)

    def test_wrong_seed_length_is_refused(self):
        with self.assertRaises(SignerUnavailableError):
            FleetSigner(b"short")


class ReceiptTests(unittest.TestCase):
    def make(self, tmp):
        signer = FleetSigner.from_state_dir(tmp)
        ledger = AnchorLedger(Path(tmp) / "ledger.jsonl")
        body = {
            "schema": RECEIPT_SCHEMA,
            "fleet_id": "fleet-test",
            "job_id": "job-0123456789abcdef",
            "work_unit": {"digest": "a" * 64},
            "result": {"sha256": sha256_hex(b"output"), "bytes": 6},
            "devices": [],
        }
        return signer, ledger, sign_receipt(body, signer, ledger)

    def test_a_signed_receipt_verifies_with_its_ledger_and_output(self):
        with state_dir() as tmp:
            signer, ledger, receipt = self.make(tmp)
            check = verify_receipt(
                receipt, public_key=signer.public_key, output=b"output", work_unit_digest="a" * 64, ledger_path=ledger.path
            )
            self.assertTrue(check.valid, check.reasons)
            self.assertEqual(receipt["signature"]["algorithm"], "ML-DSA-65")

    def test_tampering_or_the_wrong_key_invalidates_it(self):
        with state_dir() as tmp:
            signer, ledger, receipt = self.make(tmp)
            edited = json.loads(json.dumps(receipt))
            edited["result"]["bytes"] = 7
            self.assertFalse(verify_receipt(edited).valid)
            self.assertFalse(verify_receipt(receipt, output=b"other").valid)
            self.assertFalse(verify_receipt(receipt, work_unit_digest="b" * 64).valid)
            with state_dir() as other:
                stranger = FleetSigner.from_state_dir(other)
                check = verify_receipt(receipt, public_key=stranger.public_key)
                self.assertFalse(check.valid)
                self.assertTrue(any("different key" in r for r in check.reasons))
            moved = json.loads(json.dumps(receipt))
            moved["ledger_anchor"]["seq"] = 5
            self.assertFalse(verify_receipt(moved, ledger_path=ledger.path).valid)


if __name__ == "__main__":
    unittest.main()

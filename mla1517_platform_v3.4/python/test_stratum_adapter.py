"""Executable behavioural tests for the live Stratum proof boundary."""
from __future__ import annotations

import hashlib
import unittest

from mla1517.mining.stratum_adapter import (
    CassiniSealError,
    StaleJobError,
    StratumAdapterError,
    StratumProofAdapter,
    TargetError,
    sha256d,
    stratum_prevhash,
)


class StratumAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = StratumProofAdapter()
        self.adapter.handle_subscribe_result([[], "aabbccdd", 4])
        self.job_params = [
            "job-1",
            "00" * 32,
            "01000000",
            "ffffffff",
            [],
            "20000000",
            "1d00ffff",
            "65abcdef",
            True,
        ]
        self.adapter.handle_message({"method": "mining.set_target", "params": ["ff" * 32]})
        self.adapter.handle_message({"method": "mining.notify", "params": self.job_params})

    def test_subscription_retains_extranonce_contract(self) -> None:
        self.assertEqual(self.adapter.subscription.extranonce1, "aabbccdd")
        self.assertEqual(self.adapter.subscription.extranonce2_size, 4)
        self.assertEqual(self.adapter.next_extranonce2(), "00000000")

    def test_raw_subscription_response_is_validated(self) -> None:
        state = StratumProofAdapter.parse_subscribe_response(
            {"id": 1, "result": [[], "0102", 2], "error": None}
        )
        self.assertEqual(state.extranonce1, "0102")
        with self.assertRaises(StratumAdapterError):
            StratumProofAdapter.parse_subscribe_response(
                {"id": 1, "result": [[], "0102", 2], "error": [20, "rejected", None]}
            )

    def test_notify_requires_exactly_nine_fields(self) -> None:
        with self.assertRaises(StratumAdapterError):
            self.adapter.handle_message({"method": "mining.notify", "params": self.job_params[:8]})

    def test_coinbase_merkle_and_header_are_real_bytes(self) -> None:
        coinbase = bytes.fromhex("01000000" + "aabbccdd" + "00000001" + "ffffffff")
        self.assertEqual(self.adapter.build_coinbase("00000001"), coinbase)
        self.assertEqual(self.adapter.merkle_root("job-1", "00000001"), sha256d(coinbase))
        header = self.adapter.build_header("job-1", "00000001", "65abcdef", 0)
        self.assertEqual(len(header), 80)
        self.assertEqual(header[-4:], b"\x00\x00\x00\x00")
        self.assertEqual(header[4:36], b"\x00" * 32)
        self.assertEqual(header[36:68], sha256d(coinbase))

    def test_prevhash_is_swapped_by_word_not_reversed_whole(self) -> None:
        # Slush notify prevhash. The header field is eight reversed words.
        # Reversing the whole field is the displayed block hash.
        notified = "4d16b6f85af6e2198f44ae2a6de67f78487ae5611b77c6c0440b921e00000000"
        header_field = stratum_prevhash(notified)
        self.assertEqual(header_field[:4], bytes.fromhex("f8b6164d"))
        self.assertTrue(header_field[::-1].hex().startswith("00000000"))
        self.assertNotEqual(header_field, bytes.fromhex(notified)[::-1])

    def test_merkle_branch_is_concatenated_in_wire_order(self) -> None:
        branch = "11" * 32
        params = list(self.job_params)
        params[4] = [branch]
        self.adapter.handle_message({"method": "mining.notify", "params": params})
        coinbase = self.adapter.build_coinbase("00000001")
        expected = sha256d(sha256d(coinbase) + bytes.fromhex(branch))
        self.assertEqual(self.adapter.merkle_root("job-1", "00000001"), expected)

    def test_dropped_session_cannot_build_a_header(self) -> None:
        self.adapter.drop_session()
        with self.assertRaises(StratumAdapterError):
            self.adapter.build_header("job-1", "00000001", "65abcdef", 0)

    def test_target_checked_submission_parameters(self) -> None:
        params = self.adapter.submission_params(
            worker_name="worker.test",
            job_id="job-1",
            extranonce2="00000001",
            ntime="65abcdef",
            nonce=0,
        )
        self.assertEqual(params, ["worker.test", "job-1", "00000001", "65abcdef", "00000000"])

    def test_low_target_rejects_candidate(self) -> None:
        self.adapter.handle_message({"method": "mining.set_target", "params": ["00" * 31 + "01"]})
        with self.assertRaises(TargetError):
            self.adapter.submission_params(
                worker_name="worker.test",
                job_id="job-1",
                extranonce2="00000001",
                ntime="65abcdef",
                nonce=0,
            )

    def test_clean_job_rejects_old_job(self) -> None:
        next_job = list(self.job_params)
        next_job[0] = "job-2"
        self.adapter.handle_message({"method": "mining.notify", "params": next_job})
        with self.assertRaises(StaleJobError):
            self.adapter.build_header("job-1", "00000001", "65abcdef", 0)

    def test_invalid_cassini_seal_fails_closed(self) -> None:
        adapter = StratumProofAdapter(cassini_validator=lambda _job, _ex2, _nonce: False)
        adapter.handle_subscribe_result([[], "aabbccdd", 4])
        adapter.handle_message({"method": "mining.set_target", "params": ["ff" * 32]})
        adapter.handle_message({"method": "mining.notify", "params": self.job_params})
        with self.assertRaises(CassiniSealError):
            adapter.validate_candidate(
                job_id="job-1", extranonce2="00000001", ntime="65abcdef", nonce=0
            )

    def test_set_extranonce_replaces_the_subscription(self) -> None:
        self.adapter.handle_message(
            {"method": "mining.set_extranonce", "params": ["eeff", 2]}
        )
        self.assertEqual(self.adapter.subscription.extranonce1, "eeff")
        self.assertEqual(self.adapter.subscription.extranonce2_size, 2)
        self.assertEqual(self.adapter.next_extranonce2(), "0000")

    def test_digest_is_independently_recomputable(self) -> None:
        proof = self.adapter.validate_candidate(
            job_id="job-1", extranonce2="00000001", ntime="65abcdef", nonce=0
        )
        self.assertEqual(proof.digest, hashlib.sha256(hashlib.sha256(proof.header).digest()).digest())


if __name__ == "__main__":
    unittest.main()

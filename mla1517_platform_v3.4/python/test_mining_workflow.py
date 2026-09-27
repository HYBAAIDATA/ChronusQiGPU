"""Handshake, target gate, reconnect, and share digest."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mla1517.mining.stratum_adapter import StratumProofAdapter, TargetError
from mla1517.mining.workflow import MiningWorkflow, SessionDown, payload_matches, store_share


class MiningWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.flow = MiningWorkflow()
        self.flow.connect()
        self.flow.adapter.handle_subscribe_result([[], "aabbccdd", 4])
        self.flow.authorize(True)
        self.flow.adapter.handle_message({"method": "mining.set_target", "params": ["ff" * 32]})
        self.flow.adapter.handle_message(
            {
                "method": "mining.notify",
                "params": [
                    "job-1",
                    "00" * 32,
                    "01000000",
                    "ffffffff",
                    [],
                    "20000000",
                    "1d00ffff",
                    "65abcdef",
                    True,
                ],
            }
        )

    def test_submit_is_refused_until_the_handshake_is_back(self) -> None:
        self.flow.disconnect()
        with self.assertRaises(SessionDown):
            self.flow.submit(
                worker_name="w",
                job_id="job-1",
                extranonce2="00000001",
                ntime="65abcdef",
                nonce=0,
            )
        self.flow.connect()
        self.flow.adapter.handle_subscribe_result([[], "aabbccdd", 4])
        with self.assertRaises(SessionDown):
            self.flow.submit(
                worker_name="w",
                job_id="job-1",
                extranonce2="00000001",
                ntime="65abcdef",
                nonce=0,
            )

    def test_submit_params_only_when_the_header_meets_the_target(self) -> None:
        params = self.flow.submit(
            worker_name="w",
            job_id="job-1",
            extranonce2="00000001",
            ntime="65abcdef",
            nonce=0,
        )
        self.assertEqual(params[0], "w")
        self.flow.adapter.handle_message({"method": "mining.set_target", "params": ["00" * 31 + "01"]})
        with self.assertRaises(TargetError):
            self.flow.submit(
                worker_name="w",
                job_id="job-1",
                extranonce2="00000001",
                ntime="65abcdef",
                nonce=0,
            )

    def test_stored_share_rejects_a_forged_payload(self) -> None:
        proof = self.flow.prove(
            job_id="job-1", extranonce2="00000001", ntime="65abcdef", nonce=0
        )
        with tempfile.TemporaryDirectory() as directory:
            certificate = store_share(directory, proof, accepted=True)
        self.assertTrue(payload_matches(certificate, certificate.payload))
        forged = certificate.payload.replace(b'"accepted": true', b'"accepted": false')
        self.assertFalse(payload_matches(certificate, forged))
        self.assertGreaterEqual(certificate.address_index, 1)


if __name__ == "__main__":
    unittest.main()

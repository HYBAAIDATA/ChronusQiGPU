"""Pool topology bookkeeping: failover roster, attempts, selections (§3).

The coordinator records only what actually happened — connect attempts,
refusals with the failing stage, and the selected endpoint. The snapshot is
what ``/api/v1/stratum/status`` relays as ``pool`` for the ops surface.
"""

from __future__ import annotations

import os
import unittest

from chronus.mla1517.mining.coordinator import IntelligentPoolCoordinator
from chronus.mla1517.mining.session import MiningSession
from manifold_pool_coordinator import PoolEndpoint


def _coordinator() -> IntelligentPoolCoordinator:
    # The default "hendrix" nonce order needs an optional dependency; "m32"
    # keeps the lane order without it — same convention as the loop tests.
    os.environ.setdefault("PYTHIA_NONCE_ORDER", "m32")
    endpoints = [
        PoolEndpoint(host="stratum.braiins.test", port=3333, name="braiins"),
        PoolEndpoint(host="stratum.viabtc.test", port=443, name="viabtc", tls=True),
    ]
    return IntelligentPoolCoordinator(
        endpoints,
        username="rig.worker",
        password="x",
        submit_enabled=False,
        mining_session=MiningSession(cooldown_seconds=0),
    )


class PoolTopologyTests(unittest.TestCase):
    def test_snapshot_starts_empty_without_attempts(self) -> None:
        pool = _coordinator()._pool_snapshot()
        self.assertEqual(pool["schema"], "pythia.pool_topology/1")
        self.assertEqual(len(pool["endpoints"]), 2)
        self.assertEqual(pool["endpoints"][0]["endpoint"], "stratum.braiins.test:3333")
        self.assertTrue(pool["endpoints"][1]["tls"])
        self.assertIsNone(pool["active"])
        self.assertEqual(pool["connect_attempts"], 0)
        self.assertIsNone(pool["last_error"])
        self.assertEqual(pool["history"], [])

    def test_worker_identity_is_redacted(self) -> None:
        pool = _coordinator()._pool_snapshot()
        self.assertEqual(pool["endpoints"][0]["worker"], "ri***")
        self.assertNotIn("rig.worker", repr(pool))

    def test_refusal_and_selection_are_recorded_in_order(self) -> None:
        import types

        coord = _coordinator()
        refused = coord.endpoints[1]
        coord._pool_attempt_record()
        coord._pool_refusal_record(refused, "connect", "timed out")
        coord._pool_attempt_record()
        coord._pool_selected_record(coord.endpoints[0], 0, 2, ["viabtc: timed out"])
        # The bound client marks the active endpoint — set it as
        # connect_with_failover does after a successful bind.
        coord.client = types.SimpleNamespace(endpoint=coord.endpoints[0])
        pool = coord._pool_snapshot()

        self.assertEqual(pool["connect_attempts"], 2)
        self.assertEqual(pool["active"], "braiins")
        self.assertEqual(pool["endpoint_index"], 0)
        self.assertEqual(pool["last_selected"]["attempt"], 2)
        self.assertIsNone(pool["last_error"])
        self.assertEqual([entry["event"] for entry in pool["history"]], ["refused", "selected"])
        self.assertEqual(pool["history"][0]["stage"], "connect")
        self.assertEqual(pool["history"][1]["previous_failures"], ["viabtc: timed out"])

    def test_selection_clears_the_last_error(self) -> None:
        coord = _coordinator()
        coord._pool_refusal_record(coord.endpoints[1], "connect", "refused")
        coord._pool_selected_record(coord.endpoints[0], 0, 2, [])
        self.assertIsNone(coord._pool_snapshot()["last_error"])

    def test_history_is_bounded(self) -> None:
        coord = _coordinator()
        for _ in range(30):
            coord._pool_refusal_record(coord.endpoints[1], "connect", "refused")
        self.assertEqual(len(coord._pool_snapshot()["history"]), 24)


if __name__ == "__main__":
    unittest.main()

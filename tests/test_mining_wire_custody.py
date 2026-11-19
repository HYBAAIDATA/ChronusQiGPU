"""Real local TCP, SHA-256d and encrypted custody; no external pool evidence."""
import asyncio
import base64
import hashlib
import json
import os
from fractions import Fraction
from pathlib import Path

import pytest

from chronus.execution.asic_sha256 import sha256d_unrolled
from chronus.execution.authority import _unseal
from chronus.storage.durable import DurableTheseusService
from chronus.stratum.gateway import StratumGateway

pytestmark = pytest.mark.real

CORPUS = Path(__file__).parent / "vectors" / "mainnet_975565_976064.json"


def test_independent_full_sha256d_on_all_mainnet_headers():
    rows = json.loads(CORPUS.read_text(encoding="utf-8"))["blocks"]
    assert len(rows) == 500
    for row in rows:
        header = bytes.fromhex(row["header_hex"])
        digest = sha256d_unrolled(header)
        assert digest == hashlib.sha256(hashlib.sha256(header).digest()).digest()
        assert digest[::-1].hex() == row["block_hash_be"]


def test_correlated_wire_acknowledgements_and_unresolved_reopen(mining_custody, monkeypatch):  # mock-ok: configure actual TCP endpoint only
    # mock-ok: only configures a real loopback endpoint; no execution replaced
    async def scenario():
        seen = []
        frames = []
        done = asyncio.Event()

        async def pool(reader, writer):
            try:
                for i in range(3):
                    raw = await reader.readline()
                    req = json.loads(raw)
                    seen.append(req)
                    assert req["method"] == "mining.submit"
                    if i == 0:
                        frame = ('{ "id": %d, "result": true, "error": null }\r\n' % req["id"]).encode()
                    elif i == 1:
                        frame = ('{"id":%d,"result":false,"error":[21,"stale",null]}\n' % req["id"]).encode()
                    else:
                        done.set()
                        break
                    frames.append(frame)
                    writer.write(frame)
                    await writer.drain()
                await reader.read()
            finally:
                writer.close()
                await writer.wait_closed()

        server = await asyncio.start_server(pool, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        monkeypatch.setenv("CHRONUS_ALLOWED_POOL_ENDPOINTS", json.dumps([f"stratum+tcp://127.0.0.1:{port}"]))  # mock-ok: actual loopback allowlist
        gw = StratumGateway("127.0.0.1", port, "worker", "x", pool_timeout_sec=5)
        try:
            await gw.connect()
            gw.current_difficulty = Fraction(1, 10**100)
            gw._process_notify(["job", "00" * 32, "01000000", "00000000", [],
                                "20000000", "207fffff", "60000000", True])
            policy = gw.submission_policy
            policy.arm("local-custody-test", 3)
            params = ["worker", "job", "00000000", "60000000", "00000000"]
            result = await gw.send_rpc("mining.submit", params)
            assert result["result"] is True
            params[4] = "00000001"
            reject_id = await gw.write_rpc("mining.submit", params)
            assert (await gw.read_message())["result"] is False
            params[4] = "00000002"
            unresolved_id = await gw.write_rpc("mining.submit", params)
            await asyncio.wait_for(done.wait(), 5)
            assert policy.accepted == 1 and policy.pending == {unresolved_id}
            await gw.close()
            assert not policy.pending
            assert not policy.armed
            store = DurableTheseusService(os.environ["CHRONUS_MINING_CUSTODY_PATH"])
            tenant = os.environ["CHRONUS_MINING_TENANT_ID"]
            key = Path(os.environ["CHRONUS_MINING_KEY_FILE"]).read_bytes()
            assert store.verify_journal_continuity(tenant)
            records = [(entry.event_type, _unseal(store.reconstruct(tenant, entry.object_id), key, tenant))
                       for entry in store.get_journal(tenant)]
            sent = [r for e, r in records if e == "MINING_SUBMIT_AUTHORIZED"]
            assert [r["candidate"]["submission_params"] for r in sent] == [r["params"] for r in seen]
            acks = [r for e, r in records if e == "MINING_POOL_ACKNOWLEDGEMENT"]
            assert len(acks) == 2
            assert [r["accepted"] for r in acks] == [True, False]
            assert acks[1]["rpc_id"] == reject_id
            for ack, frame in zip(acks, frames):
                assert ack["response_evidence_class"] == "RECEIVED_STRATUM_FRAME"
                assert base64.b64decode(ack["wire_frame_b64"], validate=True) == frame
                assert ack["wire_frame_sha256"] == hashlib.sha256(frame).hexdigest()
            unanswered = [r for e, r in records if e == "MINING_SUBMISSIONS_UNRESOLVED"]
            assert len(unanswered) == 1
            assert unanswered[0]["rpc_ids"] == [unresolved_id]
            assert unanswered[0]["verdict"] == "UNRESOLVED"
        finally:
            await gw.close()
            server.close()
            await server.wait_closed()

    asyncio.run(scenario())

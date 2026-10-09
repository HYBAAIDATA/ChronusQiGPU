"""Share liveness vs. block low-profile rules in MiningSession.

Shares (accepted, rejected or unknown) never park the miner and are never
submitted twice. Block candidates keep the external-chain gate, so the miner
never mines two consecutive blocks.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from manifold_pool_coordinator import PoolEndpoint, StratumClient
from chronus.mla1517.mining.session import SHARE_LOG_LIMIT, MiningSession, digest

MAX_TARGET = 2**256 - 1
PARENT = bytes(range(32))


def _header(nonce: int) -> bytes:
    return b"\x00\x00\x00\x20" + PARENT + bytes(32) + b"\x00" * 8 + nonce.to_bytes(4, "little")


def _submit(session: MiningSession, nonce: int, *, block: bool = False) -> bytes:
    header = _header(nonce)
    session.begin_submission(
        header=header,
        target=MAX_TARGET,
        job_id="job",
        parent_hash=PARENT[::-1].hex(),
        parent_height=900_000,
        block_candidate=block,
        submission_id=f"submission:{nonce}",
    )
    return header


@pytest.mark.parametrize("outcome", [True, False, None])
def test_every_share_outcome_returns_to_searching(tmp_path, outcome):
    session = MiningSession(tmp_path / "s.json", cooldown_seconds=3600)
    header = _submit(session, 1)
    session.submission_finished(outcome)
    assert session.state == "SEARCHING"
    assert session.history == ["SEARCHING"] and session.cycles == 0
    assert session.last_share["outcome"] is outcome
    assert session.last_share["submission_id"] == "submission:1"
    assert session.already_submitted(digest(header)[::-1].hex())
    assert len(session.memory.records) == (1 if outcome is True else 0)
    session.close()


def test_unwritten_share_intent_rolls_back_without_poisoning_duplicate_guard(tmp_path):
    session = MiningSession(tmp_path / "s.json")
    header = _submit(session, 22)
    digest_hex = digest(header)[::-1].hex()
    session.submission_not_written()
    assert session.state == "SEARCHING"
    assert session.pending is None
    assert session.share_log == []
    assert not session.already_submitted(digest_hex)

    # A transport-proven zero-write may be retried under a fresh identity
    # check; the lifecycle itself does not mislabel it UNKNOWN.
    _submit(session, 22)
    session.submission_finished(False)
    assert session.already_submitted(digest_hex)
    session.close()


def test_crash_mid_share_resolves_as_unknown_and_keeps_mining(tmp_path):
    path = tmp_path / "s.json"
    session = MiningSession(path)
    header = _submit(session, 2)
    session.close()
    restored = MiningSession(path)
    assert restored.state == "SUBMITTING"
    restored.submission_finished(None)
    assert restored.state == "SEARCHING"
    assert restored.already_submitted(digest(header)[::-1].hex())
    restored.close()


def test_unknown_block_candidate_keeps_the_low_profile_gate():
    session = MiningSession(cooldown_seconds=0)
    _submit(session, 3, block=True)
    session.submission_finished(None)
    assert session.state == "WAITING_EXTERNAL"
    assert session.share_log == []


def test_accepted_block_forbids_mining_directly_on_it(tmp_path):
    session = MiningSession(cooldown_seconds=0)
    header = _submit(session, 4, block=True)
    session.submission_finished(True)
    assert session.state == "WAITING_EXTERNAL"
    assert session.last_block_hash == digest(header)[::-1].hex()


def test_share_log_is_bounded_and_durable(tmp_path):
    path = tmp_path / "s.json"
    session = MiningSession(path)
    for nonce in range(SHARE_LOG_LIMIT + 5):
        _submit(session, 100 + nonce)
        session.submission_finished(nonce % 3 == 0 or None)
    assert len(session.share_log) == SHARE_LOG_LIMIT
    session.close()
    restored = MiningSession(path)
    assert len(restored.share_log) == SHARE_LOG_LIMIT
    assert restored.share_log[-1]["submission_id"] == f"submission:{100 + SHARE_LOG_LIMIT + 4}"
    restored.close()


def test_round_two_single_share_file_restores(tmp_path):
    path = tmp_path / "s.json"
    session = MiningSession(path)
    _submit(session, 7)
    session.submission_finished(True)
    session.close()
    data = json.loads(path.read_text())
    data["last_share"] = data.pop("share_log")[-1]
    path.write_text(json.dumps(data))
    restored = MiningSession(path)
    assert restored.last_share["submission_id"] == "submission:7"
    restored.close()


@pytest.mark.parametrize("outcome", [True, False, None])
def test_share_parked_by_an_older_build_resumes_on_restart(tmp_path, outcome):
    path = tmp_path / "s.json"
    session = MiningSession(path)
    header = _submit(session, 8)
    session.close()
    data = json.loads(path.read_text())
    data["pending"]["outcome"] = outcome
    data["state"] = "WAITING_EXTERNAL"
    data["history"] = ["SEARCHING", "SUBMITTING", "WAITING_EXTERNAL"]
    data.pop("share_log")
    path.write_text(json.dumps(data))
    restored = MiningSession(path)
    assert restored.state == "SEARCHING" and restored.pending is None
    assert restored.already_submitted(digest(header)[::-1].hex())
    assert restored.last_share["outcome"] is outcome
    restored.close()
    assert json.loads(path.read_text())["state"] == "SEARCHING"


def test_malformed_share_log_is_refused(tmp_path):
    path = tmp_path / "s.json"
    MiningSession(path).close()
    data = json.loads(path.read_text())
    data["share_log"] = [{"block_hash": 5, "outcome": "maybe"}]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="share log"):
        MiningSession(path)


async def _early_notify() -> None:
    notify = ["job-early", "ab" * 32, "aa", "bb", [], "00000001", "1a0bb4f4", "5f3f2a1e", True]

    async def handler(reader, writer):
        try:
            while line := await reader.readline():
                request = json.loads(line)
                if request["method"] == "mining.subscribe":
                    result = [[], "00", 4]
                    writer.write(
                        (json.dumps({"id": request["id"], "result": result}) + "\n").encode()
                    )
                    note = {"id": None, "method": "mining.notify", "params": notify}
                    writer.write((json.dumps(note) + "\n").encode())
                elif request["method"] == "mining.authorize":
                    writer.write(
                        (json.dumps({"id": request["id"], "result": True}) + "\n").encode()
                    )
                    target = {"id": None, "method": "mining.set_target", "params": ["ff" * 32]}
                    writer.write((json.dumps(target) + "\n").encode())
                await writer.drain()
        finally:
            writer.close()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    endpoint = PoolEndpoint("127.0.0.1", server.sockets[0].getsockname()[1], "early")
    client = StratumClient(endpoint, username="w", password="x", request_timeout=5.0)
    try:
        await asyncio.wait_for(client.connect(), 5)
        for _ in range(100):
            if client.runtime_state.ready:
                break
            await asyncio.sleep(0.01)
        generation = client.runtime_state.current_job
        assert generation is not None and generation.job_id == "job-early"
        assert client.runtime_state.ready and client.runtime_state.session_id
    finally:
        await client.close()
        server.close()
        await server.wait_closed()


def test_notify_before_subscribe_response_is_consumed_registers_generation():
    asyncio.run(_early_notify())

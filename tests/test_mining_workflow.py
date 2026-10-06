import asyncio
import io
import json

import pytest

from chronus.seam.workflow import LAYER_IDS, PASS_MEANS, run_workflow


async def _pool(host="127.0.0.1"):
    async def handle(reader, writer):
        while True:
            line = await reader.readline()
            if not line:
                break
            msg = json.loads(line.decode())
            mid = msg.get("id")
            method = msg.get("method")
            if method == "mining.subscribe":
                writer.write(
                    (
                        json.dumps(
                            {
                                "id": mid,
                                "result": [[["mining.notify", "sub"]], "abcd", 4],
                                "error": None,
                            }
                        )
                        + "\n"
                    ).encode()
                )
                await writer.drain()
            elif method == "mining.authorize":
                writer.write(
                    (json.dumps({"id": mid, "result": True, "error": None}) + "\n").encode()
                )
                await writer.drain()
                writer.write(
                    (
                        json.dumps(
                            {
                                "id": None,
                                "method": "mining.set_difficulty",
                                "params": [0.000000001],
                            }
                        )
                        + "\n"
                    ).encode()
                )
                writer.write(
                    (
                        json.dumps(
                            {
                                "id": None,
                                "method": "mining.notify",
                                "params": [
                                    "job-e2e",
                                    "00" * 32,
                                    "01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff",
                                    "ffffffff0100f2052a010000001976a914000000000000000000000000000000000000000088ac00000000",
                                    [],
                                    "20000000",
                                    "1d00ffff",
                                    "29ab5f49",
                                    True,
                                ],
                            }
                        )
                        + "\n"
                    ).encode()
                )
                await writer.drain()
            elif method == "mining.submit":
                writer.write(
                    (json.dumps({"id": mid, "result": True, "error": None}) + "\n").encode()
                )
                await writer.drain()
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

    server = await asyncio.start_server(handle, host, 0)
    port = server.sockets[0].getsockname()[1]
    return server, port


async def _bounded(coro, seconds: float):
    """Run ``coro``; if it stalls, fail with the stack of every pending task."""
    task = asyncio.ensure_future(coro)
    done, _ = await asyncio.wait({task}, timeout=seconds)
    if not done:
        stacks = io.StringIO()
        for pending in asyncio.all_tasks():
            if pending is not asyncio.current_task():
                print(f"--- {pending.get_coro()}", file=stacks)
                pending.print_stack(file=stacks)
        task.cancel()
        raise AssertionError(f"workflow stalled for {seconds}s; pending:\n{stacks.getvalue()}")
    return task.result()


def test_full_workflow_one_job():
    async def _run():
        server, port = await _pool()
        async with server:
            return await run_workflow(
                "127.0.0.1",
                port,
                "pythia",
                "x",
                window=64,
                heal=True,
                attest_key=b"test-workflow-custody",
            )

    result = asyncio.run(_bounded(_run(), 60.0))
    result.assert_all()
    assert result.accepted is True
    assert set(PASS_MEANS) == set(LAYER_IDS)
    assert result.extra["forgery_rejected"] is True
    assert result.extra["attest_scheme"] == "hmac-sha256"
    assert result.extra["stale_extranonce1"] != ""
    assert result.extra["live_extranonce1"] != ""
    for layer in LAYER_IDS:
        verdict = result.verdicts[layer]
        assert verdict.passed is True, f"{layer} FAIL: {verdict.detail}"
        assert f"{layer} PASS" in "\n".join(result.logs)
    payload = result.to_dict()
    assert payload["layers"] == list(LAYER_IDS)
    assert all(payload["verdicts"][name]["passed"] for name in LAYER_IDS)


def test_full_workflow_binds_the_certificate_into_a_chained_ledger(tmp_path):
    """custody_dir → HMAC'd EvidenceLedger record + durable HyperscalerSku."""

    async def _run():
        server, port = await _pool()
        async with server:
            return await run_workflow(
                "127.0.0.1",
                port,
                "pythia",
                "x",
                window=64,
                heal=True,
                attest_key=b"test-workflow-custody",
                custody_dir=tmp_path / "custody",
            )

    result = asyncio.run(_bounded(_run(), 60.0))
    result.assert_all()
    assert result.extra["custody_state"].startswith("chained:")
    assert result.extra["ledger_chain_digest"]

    from chronus.virtual_igpu.evidence import EvidenceLedger
    from aethel.storage import AddressSpace

    ledger_root = tmp_path / "custody" / "seam-attest"
    ledger_file = ledger_root / "evidence_ledger.jsonl"
    assert ledger_file.exists()
    # Re-loading under the same key re-verifies chain + HMAC.
    EvidenceLedger(ledger_root, hmac_key=b"test-workflow-custody")
    # Re-loading under the wrong key fails closed on the HMAC.
    with pytest.raises(ValueError):
        EvidenceLedger(ledger_root, hmac_key=b"attacker-key")
    # A tampered record fails chain verification on reload.
    lines = ledger_file.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[-1])
    record["result"]["nonce"] = "deadbeef"
    lines[-1] = json.dumps(record, sort_keys=True)
    ledger_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        EvidenceLedger(ledger_root, hmac_key=b"test-workflow-custody")

    # The certificate store's snapshot is durable: journal + blocks on disk,
    # replayable through AddressSpace.attach.
    snapshot_root = tmp_path / "custody" / "hyperscaler"
    assert (snapshot_root / "ledger.jsonl").exists()
    assert any((snapshot_root / "blocks").iterdir())
    AddressSpace.attach(snapshot_root)


def test_full_workflow_fails_closed_without_an_attest_key(monkeypatch):
    """No custody key → L8 records FAIL, never an unkeyed signature."""
    for name in (
        "PYTHIA_SEAM_ATTEST_KEY_HEX",
        "PYTHIA_SEAM_ATTEST_KEY",
        "PYTHIA_IDENTITY_HMAC_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)

    async def _run():
        server, port = await _pool()
        async with server:
            return await run_workflow(
                "127.0.0.1",
                port,
                "pythia",
                "x",
                window=64,
                heal=True,
                fail_fast=False,
            )

    with pytest.raises(AssertionError, match="L8_attest.*custody key"):
        asyncio.run(_bounded(_run(), 60.0))


def test_waiting_for_a_job_honours_its_timeout_when_the_pool_is_silent():
    from mining.stratum_bridge import StratumBridge

    async def silent(reader, writer):
        await reader.read()  # accept, then say nothing until the client leaves
        # On Python 3.12 an unclosed handler connection holds `async with server`.
        writer.close()

    async def _run():
        server = await asyncio.start_server(silent, "127.0.0.1", 0)
        async with server:
            bridge = StratumBridge("127.0.0.1", server.sockets[0].getsockname()[1])
            await bridge.connect()
            started = asyncio.get_running_loop().time()
            try:
                await bridge.wait_for_job(timeout=0.3)
            except TimeoutError:
                return asyncio.get_running_loop().time() - started
            finally:
                await bridge.disconnect()
        return None

    waited = asyncio.run(_bounded(_run(), 10.0))
    assert waited is not None and waited < 2.0

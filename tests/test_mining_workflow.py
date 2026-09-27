import asyncio
import json

from igpu.seam.workflow import LAYER_IDS, PASS_MEANS, run_workflow


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
                writer.write((json.dumps({"id": mid, "result": True, "error": None}) + "\n").encode())
                await writer.drain()
                writer.write(
                    (
                        json.dumps(
                            {
                                "id": None,
                                "method": "mining.set_difficulty",
                                "params": [0.000001],
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
                writer.write((json.dumps({"id": mid, "result": True, "error": None}) + "\n").encode())
                await writer.drain()
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

    server = await asyncio.start_server(handle, host, 0)
    port = server.sockets[0].getsockname()[1]
    return server, port


def test_full_workflow_one_job():
    async def _run():
        server, port = await _pool()
        async with server:
            return await run_workflow("127.0.0.1", port, "pythia", "x", window=64, heal=True)

    result = asyncio.run(_run())
    result.assert_all()
    assert result.accepted is True
    assert set(PASS_MEANS) == set(LAYER_IDS)
    assert result.extra["forgery_rejected"] is True
    assert result.extra["stale_extranonce1"] != ""
    assert result.extra["live_extranonce1"] != ""
    for layer in LAYER_IDS:
        verdict = result.verdicts[layer]
        assert verdict.passed is True, f"{layer} FAIL: {verdict.detail}"
        assert f"{layer} PASS" in "\n".join(result.logs)
    payload = result.to_dict()
    assert payload["layers"] == list(LAYER_IDS)
    assert all(payload["verdicts"][name]["passed"] for name in LAYER_IDS)

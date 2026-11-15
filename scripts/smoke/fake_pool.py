"""scripts/smoke/fake_pool.py — local Stratum V1 pool for offline smoke.

Share difficulty is ~2^-24 of Bitcoin diff1 via set_difficulty, so a share
lands in ~256 hashes and the submit returns a literal true. nbits stays a
harder network target. Canonical little-endian target comparison, matching a
real pool (and the smoke client).

    python scripts/smoke/fake_pool.py --port 3333 --exit-after 1
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys

NBITS = "207fffff"           # network target, deliberately harder than the share target
DIFF1 = 0xFFFF << (8 * (0x1D - 3))
# ~2^-24 of diff1 → expected ~256 SHA-256d tries under DIFF1 // difficulty.
DIFFICULTY = 1 / (1 << 24)
TARGET = int(DIFF1 // DIFFICULTY)
JOB_ID = "smokejob1"
VERSION = "20000000"
PREVHASH = "00" * 31 + "01"
COINB1 = "01000000" + "01" + "00" * 31 + "ffffffff" + "01" + "00f2052a01000000" + "0151"
COINB2 = "ffffffff" + "01000000"


def header(extranonce1: str, params: list) -> bytes:
    _, _job, en2, ntime, nonce = params
    coinbase = bytes.fromhex(COINB1 + extranonce1 + en2 + COINB2)
    root = hashlib.sha256(hashlib.sha256(coinbase).digest()).digest()
    raw = bytes.fromhex(PREVHASH)
    return (int(VERSION, 16).to_bytes(4, "little")
            + b"".join(raw[i:i + 4][::-1] for i in range(0, 32, 4))
            + root
            + int(ntime, 16).to_bytes(4, "little")
            + int(NBITS, 16).to_bytes(4, "little")
            + int(nonce, 16).to_bytes(4, "little"))


def make_handler(extranonce1: str):
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                line = await reader.readline()
                if not line:
                    return
                message = json.loads(line)
                method, params, ident = message.get("method"), message.get("params", []), message.get("id")
                if method == "mining.configure":
                    reply = {"id": ident, "error": None,
                             "result": {"version-rolling": True,
                                        "version-rolling.mask": "1fffe000"}}
                elif method == "mining.subscribe":
                    reply = {"id": ident, "error": None,
                             "result": [[["mining.notify", "smoke"]], extranonce1, 4]}
                elif method == "mining.authorize":
                    writer.write((json.dumps({"id": ident, "result": True, "error": None}) + "\n").encode())
                    for note in (
                        {"id": None, "method": "mining.set_difficulty", "params": [DIFFICULTY]},
                        {"id": None, "method": "mining.notify",
                         "params": [JOB_ID, PREVHASH, COINB1, COINB2, [], VERSION,
                                    NBITS, "67000000", True]},
                    ):
                        writer.write((json.dumps(note) + "\n").encode())
                    await writer.drain()
                    continue
                elif method == "mining.submit":
                    digest = hashlib.sha256(hashlib.sha256(header(extranonce1, params)).digest()).digest()
                    ok = int.from_bytes(digest, "little") <= TARGET
                    reply = {"id": ident, "result": True if ok else False,
                             "error": None if ok else [23, "low difficulty share", None]}
                else:
                    reply = {"id": ident, "result": None, "error": [20, f"unknown {method}", None]}
                writer.write((json.dumps(reply) + "\n").encode())
                await writer.drain()
        finally:
            writer.close()
    return handle


async def serve(port: int, exit_after: int | None) -> None:
    server = await asyncio.start_server(make_handler("deadbeef"), "127.0.0.1", port)
    print(f"fake pool on 127.0.0.1:{port}", flush=True)
    if exit_after is None:
        async with server:
            await server.serve_forever()
        return
    await asyncio.wait_for(server.serve_forever(), timeout=exit_after)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=3333)
    parser.add_argument("--exit-after", type=float, default=None)
    args = parser.parse_args()
    try:
        asyncio.run(serve(args.port, args.exit_after))
    except (KeyboardInterrupt, asyncio.TimeoutError):
        pass
    sys.exit(0)

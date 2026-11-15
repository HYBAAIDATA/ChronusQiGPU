"""scripts/smoke/fake_pool.py — local Stratum V1 pool for offline smoke.

Bitcoin difficulty 1 via set_difficulty (DIFF1). nbits stays a harder network
target. Canonical little-endian target comparison, matching a real pool and
the smoke client. Expected share work is ~2^32 SHA-256d evaluations — use the
smoke's --search geometric|opencl path (Chronus structured search / QiGPU),
or fleet scale, for wall-clock; the naive Python nonce loop is not the claim.

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
DIFFICULTY = 1
TARGET = DIFF1 // DIFFICULTY
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


def make_handler(extranonce1: str, difficulty: float, target: int):
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
                        {"id": None, "method": "mining.set_difficulty", "params": [difficulty]},
                        {"id": None, "method": "mining.notify",
                         "params": [JOB_ID, PREVHASH, COINB1, COINB2, [], VERSION,
                                    NBITS, "67000000", True]},
                    ):
                        writer.write((json.dumps(note) + "\n").encode())
                    await writer.drain()
                    continue
                elif method == "mining.submit":
                    digest = hashlib.sha256(hashlib.sha256(header(extranonce1, params)).digest()).digest()
                    ok = int.from_bytes(digest, "little") <= target
                    reply = {"id": ident, "result": True if ok else False,
                             "error": None if ok else [23, "low difficulty share", None]}
                else:
                    reply = {"id": ident, "result": None, "error": [20, f"unknown {method}", None]}
                writer.write((json.dumps(reply) + "\n").encode())
                await writer.drain()
        finally:
            writer.close()
    return handle


async def serve(port: int, exit_after: float | None, difficulty: float) -> None:
    if difficulty <= 0:
        raise ValueError("difficulty must be positive")
    target = int(DIFF1 // difficulty)
    server = await asyncio.start_server(
        make_handler("deadbeef", difficulty, target), "127.0.0.1", port
    )
    print(
        f"fake pool on 127.0.0.1:{port} difficulty={difficulty} "
        f"target_hex={target:064x} (LE compare)",
        flush=True,
    )
    if exit_after is None:
        async with server:
            await server.serve_forever()
        return
    await asyncio.wait_for(server.serve_forever(), timeout=exit_after)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=3333)
    parser.add_argument("--exit-after", type=float, default=None)
    parser.add_argument(
        "--difficulty",
        type=float,
        default=DIFFICULTY,
        help="Bitcoin-style share difficulty (default 1 ≈ 2^32 expected hashes)",
    )
    args = parser.parse_args()
    try:
        asyncio.run(serve(args.port, args.exit_after, args.difficulty))
    except (KeyboardInterrupt, asyncio.TimeoutError):
        pass
    sys.exit(0)

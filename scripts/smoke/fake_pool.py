"""scripts/smoke/fake_pool.py — local Stratum V1 pool for offline smoke.

Share difficulty defaults to 1/2**24 (easy offline accept). nbits encodes a
harder network target (smaller than the share target). Canonical little-endian
target comparison, matching a real pool and the smoke client.

    python scripts/smoke/fake_pool.py --port 3333 --exit-after 30
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from fractions import Fraction

# Compact target harder than Bitcoin difficulty 1 (DIFF1 = 0x1d00ffff decoded).
NBITS = "1c00ffff"
DIFF1 = 0xFFFF << (8 * (0x1D - 3))
DIFFICULTY = 1 / 2**24
TARGET = int(Fraction(DIFF1) / Fraction(DIFFICULTY))
JOB_ID = "smokejob1"
VERSION = "20000000"
PREVHASH = "00" * 31 + "01"
NTIME = "67000000"
COINB1 = "01000000" + "01" + "00" * 31 + "ffffffff" + "01" + "00f2052a01000000" + "0151"
COINB2 = "ffffffff" + "01000000"
_HEX = frozenset("0123456789abcdefABCDEF")


def network_target(nbits: str = NBITS) -> int:
    raw = int(nbits, 16)
    return (raw & 0xFFFFFF) << (8 * ((raw >> 24) - 3))


def _is_hex(text: object, length: int | None = None) -> bool:
    return (
        isinstance(text, str)
        and len(text) % 2 == 0
        and set(text) <= _HEX
        and (length is None or len(text) == length)
    )


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


def accept_share(extranonce1: str, params: list, target: int = TARGET) -> tuple[bool, list | None]:
    """Validate submit fields and apply the LE share predicate. Used by tests.

    Accepts 5-param submits or BIP 310 6-param submits (trailing version_bits).
    """
    if not isinstance(params, list) or len(params) not in (5, 6):
        return False, [20, "Malformed submit", None]
    worker, job_id, en2, ntime, nonce = params[:5]
    if len(params) == 6 and not _is_hex(params[5], 8):
        return False, [20, "Malformed submit", None]
    if job_id != JOB_ID:
        return False, [21, "Job not found", None]
    if not isinstance(worker, str) or not worker:
        return False, [20, "Malformed submit", None]
    if not _is_hex(en2) or len(en2) != 8:
        return False, [20, "Malformed submit", None]
    if not _is_hex(ntime, 8) or ntime.lower() != NTIME:
        return False, [20, "Malformed submit", None]
    if not _is_hex(nonce, 8):
        return False, [20, "Malformed submit", None]
    digest = hashlib.sha256(hashlib.sha256(header(extranonce1, params[:5])).digest()).digest()
    ok = int.from_bytes(digest, "little") <= target
    return ok, (None if ok else [23, "low difficulty share", None])


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
                                    NBITS, NTIME, True]},
                    ):
                        writer.write((json.dumps(note) + "\n").encode())
                    await writer.drain()
                    continue
                elif method == "mining.submit":
                    ok, error = accept_share(extranonce1, params, target)
                    reply = {"id": ident, "result": True if ok else False, "error": error}
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
    target = int(Fraction(DIFF1) / Fraction(difficulty))
    if not network_target() < target:
        raise ValueError("NBITS must decode to a harder (smaller) target than the share target")
    server = await asyncio.start_server(
        make_handler("deadbeef", difficulty, target), "127.0.0.1", port
    )
    print(
        f"fake pool on 127.0.0.1:{port} difficulty={difficulty} "
        f"target_hex={target:064x} nbits={NBITS} (LE compare)",
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
    parser.add_argument(
        "--exit-after",
        type=float,
        default=None,
        help="Stop the pool after N seconds (e.g. 30 for offline smoke)",
    )
    parser.add_argument(
        "--difficulty",
        type=float,
        default=DIFFICULTY,
        help="Bitcoin-style share difficulty (default 1/2**24 for offline accept)",
    )
    args = parser.parse_args()
    try:
        asyncio.run(serve(args.port, args.exit_after, args.difficulty))
    except (KeyboardInterrupt, asyncio.TimeoutError):
        pass
    sys.exit(0)

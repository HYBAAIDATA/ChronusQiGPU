"""Scripted Stratum V1 pool for observable smoke runs.

Serves real-shaped jobs (BIP34 height in coinbase1, changing prevhash,
clean_jobs), rotates them on a timer, verifies every submit the way a pool
does (rebuilds coinbase, merkle root and header, SHA256d against the share
target it set, stale and duplicate checks) and answers true/false with a
reason, and records
every message the miner sends: one JSON line per event on stdout and in
``--log``, and a running ``--summary`` JSON file. Standard library only.

    python scripts/scripted_pool.py --port 3334 --log pool.jsonl --summary pool.json
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import secrets
import time
from pathlib import Path

EXTRANONCE1 = "01020304"
EXTRANONCE2_SIZE = 4


def coinbase1(height: int) -> str:
    push = height.to_bytes(3, "little")
    script_prefix = bytes([len(push)]) + push
    return (
        "02000000"
        + "01"
        + "00" * 32
        + "ffffffff"
        + f"{len(script_prefix) + 8:02x}"
        + script_prefix.hex()
    )


DIFF1_TARGET = 0xFFFF * 2**208
VERSION_ROLLING_MASK = 0x1FFFE000


def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def share_target(difficulty: float) -> int:
    return int(DIFF1_TARGET / difficulty)


def share_hash(job: list, extranonce1: str, extranonce2: str, ntime: str, nonce: str,
               version_bits: str | None = None) -> bytes:
    """SHA256d of the header a Stratum V1 submit describes (internal byte order)."""
    _, prevhash, coinb1, coinb2, branches, version, nbits, _, _ = job
    coinbase = bytes.fromhex(coinb1 + extranonce1 + extranonce2 + coinb2)
    root = sha256d(coinbase)
    for branch in branches:
        root = sha256d(root + bytes.fromhex(branch))
    version_int = int(version, 16)
    if version_bits is not None:
        version_int = (version_int & ~VERSION_ROLLING_MASK) | (int(version_bits, 16) & VERSION_ROLLING_MASK)
    prev = b"".join(bytes.fromhex(prevhash)[i:i + 4][::-1] for i in range(0, 32, 4))
    header = (
        version_int.to_bytes(4, "little")
        + prev
        + root
        + bytes.fromhex(ntime)[::-1]
        + bytes.fromhex(nbits)[::-1]
        + bytes.fromhex(nonce)[::-1]
    )
    return sha256d(header)


class ScriptedPool:
    def __init__(
        self, *, difficulty: float, job_interval: float, log: Path | None, summary: Path | None
    ):
        self.difficulty = difficulty
        self.job_interval = job_interval
        self.log_path = log
        self.summary_path = summary
        self.height = 900_000
        self.prevhash = secrets.token_hex(32)
        self.job_seq = 0
        self.jobs: dict[str, list] = {}
        self.seen: set[tuple] = set()
        self.job = self._next_job(new_block=True)
        self.writers: set[asyncio.StreamWriter] = set()
        self.stats = {
            "started_at": time.time(),
            "connections": 0,
            "authorized": [],
            "methods": {},
            "jobs_sent": 0,
            "submits": 0,
            "accepted": 0,
            "rejected": 0,
            "reject_reasons": {},
            "last_submit": None,
            "share_target": f"{share_target(difficulty):064x}",
        }

    def _next_job(self, *, new_block: bool) -> list:
        if new_block:
            self.height += 1
            self.prevhash = secrets.token_hex(32)
        self.job_seq += 1
        job = [
            f"smoke-{self.job_seq}",
            self.prevhash,
            coinbase1(self.height),
            "ffffffff",
            [],
            "20000000",
            "1d00ffff",
            f"{int(time.time()):08x}",
            new_block,
        ]
        if new_block:
            self.jobs.clear()  # clean_jobs: earlier work is stale
        self.jobs[job[0]] = job
        return job

    def verify_submit(self, params: list) -> tuple[bool, str, str | None]:
        try:
            _worker, job_id, extranonce2, ntime, nonce = (str(p) for p in params[:5])
            version_bits = str(params[5]) if len(params) > 5 else None
        except (TypeError, ValueError):
            return False, "malformed", None
        job = self.jobs.get(job_id)
        if job is None:
            return False, "stale-job", None
        if len(extranonce2) != EXTRANONCE2_SIZE * 2:
            return False, "bad-extranonce2-size", None
        key = (job_id, extranonce2, ntime, nonce, version_bits)
        if key in self.seen:
            return False, "duplicate", None
        try:
            digest = share_hash(job, EXTRANONCE1, extranonce2, ntime, nonce, version_bits)
        except ValueError:
            return False, "malformed-hex", None
        value = int.from_bytes(digest, "little")
        hash_hex = digest[::-1].hex()
        if value > share_target(self.difficulty):
            return False, "high-hash", hash_hex
        self.seen.add(key)
        return True, "ok", hash_hex

    def event(self, kind: str, **fields) -> None:
        record = {"t": round(time.time(), 3), "event": kind, **fields}
        line = json.dumps(record, sort_keys=True)
        print(line, flush=True)
        if self.log_path is not None:
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        if self.summary_path is not None:
            self.summary_path.write_text(json.dumps(self.stats, indent=2, sort_keys=True))

    @staticmethod
    def _line(payload: dict) -> bytes:
        return (json.dumps(payload) + "\n").encode()

    async def _send_work(self, writer: asyncio.StreamWriter) -> None:
        writer.write(
            self._line({"id": None, "method": "mining.set_difficulty", "params": [self.difficulty]})
        )
        writer.write(self._line({"id": None, "method": "mining.notify", "params": self.job}))
        await writer.drain()
        self.stats["jobs_sent"] += 1

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        self.stats["connections"] += 1
        self.event("connect", peer=str(peer))
        try:
            while line := await reader.readline():
                try:
                    message = json.loads(line)
                except ValueError:
                    self.event("malformed", raw=line[:200].decode(errors="replace"))
                    continue
                method = str(message.get("method"))
                mid = message.get("id")
                self.stats["methods"][method] = self.stats["methods"].get(method, 0) + 1
                if method == "mining.subscribe":
                    self.event("subscribe", params=message.get("params"))
                    writer.write(
                        self._line(
                            {
                                "id": mid,
                                "result": [
                                    [["mining.notify", "smoke"]],
                                    EXTRANONCE1,
                                    EXTRANONCE2_SIZE,
                                ],
                                "error": None,
                            }
                        )
                    )
                    await writer.drain()
                elif method == "mining.authorize":
                    worker = str((message.get("params") or [""])[0])
                    self.stats["authorized"].append(worker)
                    self.event("authorize", worker=worker)
                    writer.write(self._line({"id": mid, "result": True, "error": None}))
                    await writer.drain()
                    self.writers.add(writer)
                    await self._send_work(writer)
                    self.event("notify", job_id=self.job[0], height=self.height)
                elif method == "mining.submit":
                    self.stats["submits"] += 1
                    self.stats["last_submit"] = message.get("params")
                    ok, reason, hash_hex = self.verify_submit(list(message.get("params") or []))
                    if ok:
                        self.stats["accepted"] += 1
                    else:
                        self.stats["rejected"] += 1
                        reasons = self.stats["reject_reasons"]
                        reasons[reason] = reasons.get(reason, 0) + 1
                    self.event("submit", params=message.get("params"), accepted=ok,
                               reason=reason, hash=hash_hex)
                    error = None if ok else [23 if reason == "high-hash" else 21, reason, None]
                    writer.write(self._line({"id": mid, "result": ok, "error": error}))
                    await writer.drain()
                else:
                    self.event("request", method=method)
                    if mid is not None:
                        writer.write(self._line({"id": mid, "result": True, "error": None}))
                        await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            self.writers.discard(writer)
            self.event("disconnect", peer=str(peer))
            writer.close()

    async def rotate(self) -> None:
        new_block = False
        while True:
            await asyncio.sleep(self.job_interval)
            # Alternate: a fresh block (clean_jobs), then an updated template.
            new_block = not new_block
            self.job = self._next_job(new_block=new_block)
            for writer in list(self.writers):
                try:
                    await self._send_work(writer)
                except ConnectionError:
                    self.writers.discard(writer)
            self.event("notify", job_id=self.job[0], height=self.height, clean=new_block)


async def main_async(args) -> None:
    pool = ScriptedPool(
        difficulty=args.difficulty,
        job_interval=args.job_interval,
        log=Path(args.log) if args.log else None,
        summary=Path(args.summary) if args.summary else None,
    )
    server = await asyncio.start_server(pool.handle, args.host, args.port)
    pool.event("listening", host=args.host, port=args.port)
    async with server:
        await asyncio.gather(server.serve_forever(), pool.rotate())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3334)
    parser.add_argument("--difficulty", type=float, default=1e-5)
    parser.add_argument("--job-interval", type=float, default=15.0)
    parser.add_argument("--log")
    parser.add_argument("--summary")
    try:
        asyncio.run(main_async(parser.parse_args()))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

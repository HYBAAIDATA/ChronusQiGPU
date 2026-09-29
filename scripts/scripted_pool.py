"""Scripted Stratum V1 pool for observable smoke runs.

Serves real-shaped jobs (BIP34 height in coinbase1, changing prevhash,
clean_jobs), rotates them on a timer, accepts every submit and records
every message the miner sends: one JSON line per event on stdout and in
``--log``, and a running ``--summary`` JSON file. Standard library only.

    python scripts/scripted_pool.py --port 3334 --log pool.jsonl --summary pool.json
"""

from __future__ import annotations

import argparse
import asyncio
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
        self.job = self._next_job(new_block=True)
        self.writers: set[asyncio.StreamWriter] = set()
        self.stats = {
            "started_at": time.time(),
            "connections": 0,
            "authorized": [],
            "methods": {},
            "jobs_sent": 0,
            "submits": 0,
            "last_submit": None,
        }

    def _next_job(self, *, new_block: bool) -> list:
        if new_block:
            self.height += 1
            self.prevhash = secrets.token_hex(32)
        self.job_seq += 1
        return [
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
                    self.event("submit", params=message.get("params"))
                    writer.write(self._line({"id": mid, "result": True, "error": None}))
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

"""scripts/smoke/stratum_smoke.py — end-to-end Stratum V1 smoke.

Proves: TCP connect, subscribe, authorize, job receipt, and the submit/accept
round trip. Writes a transcript that doubles as a reproducible fixture
(job, extranonce1/2, target, nonce, header, digest).

Share search targets the SET_DIFFICULTY target (diff1 / difficulty), not nbits —
nbits is the network target and is ~1e12x harder than a pool share.

Exit 0 smoke passed, 2 protocol failure, 3 endpoint unreachable, 4 config error.
Against a live pool a submit usually returns error 23 "above target"; that is a
pass for framing, so exit 2 only on a malformed or uncorrelated reply. Add
--require-accept to demand a literal true.

    python scripts/smoke/stratum_smoke.py --target fake --submit-share
    python scripts/smoke/stratum_smoke.py --target braiins --job-timeout 45
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import ssl
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

PRESETS = {"braiins": ("stratum.braiins.com", 3333), "fake": ("127.0.0.1", 3333)}
EVIDENCE = Path(__file__).resolve().parents[2] / "evidence" / "smoke"
AGENT = "chronus-smoke/1.0"
DIFF1 = 0xFFFF << (8 * (0x1D - 3))
LOW_DIFFICULTY = 23


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        sys.stderr.write(f"error: {message}\n")
        sys.exit(4)


class Transcript:
    def __init__(self, target: str) -> None:
        self.stamp = time.strftime("%Y%m%dT%H%M%S")
        self.data: dict = {"schema": "chronus.smoke/1", "target": target,
                           "started": self.stamp, "steps": [], "jobs": [],
                           "set_difficulty": [], "submits": []}

    def step(self, name: str, ok: bool, detail: str = "", **extra) -> None:
        self.data["steps"].append({"step": name, "ok": ok, "detail": detail,
                                   "at_ms": round(time.monotonic() * 1000), **extra})

    def write(self) -> Path:
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        path = EVIDENCE / f"{self.data['target']}-{self.stamp}.json"
        path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
        return path


def endpoint(host: str, port: int, scheme: str = "stratum+tcp") -> tuple[str, int]:
    raw = host.strip()
    if not raw:
        raise ValueError("empty host")
    if "://" not in raw:
        raw = f"{scheme}://{raw}"
    parts = urlsplit(raw)
    if not parts.hostname:
        raise ValueError(f"no hostname in {host!r}")
    try:
        return parts.hostname, parts.port or port
    except ValueError as exc:
        raise ValueError(f"bad port in {host!r}") from exc


def endpoint_scheme(host: str) -> str:
    raw = host.strip()
    if "://" not in raw:
        return "stratum+tcp"
    scheme = urlsplit(raw).scheme.lower()
    if scheme not in ("stratum+tcp", "stratum+ssl"):
        raise ValueError(f"unsupported scheme {scheme!r} in {host!r}")
    return scheme


def target_from_nbits(nbits: str) -> int:
    raw = int(nbits, 16)
    return (raw & 0xFFFFFF) << (8 * ((raw >> 24) - 3))


def target_from_difficulty(difficulty: float) -> int:
    if not difficulty or difficulty <= 0:
        return 0
    return int(DIFF1 // difficulty)


def prevhash_to_header(prevhash: str) -> bytes:
    raw = bytes.fromhex(prevhash)
    if len(raw) != 32:
        raise ValueError(f"prevhash is {len(raw)} bytes")
    return b"".join(raw[i:i + 4][::-1] for i in range(0, 32, 4))


def merkle_root(coinb1: str, extranonce1: str, extranonce2: str, coinb2: str,
                branch: list[str]) -> bytes:
    root = hashlib.sha256(hashlib.sha256(
        bytes.fromhex(coinb1 + extranonce1 + extranonce2 + coinb2)).digest()).digest()
    for node in branch:
        root = hashlib.sha256(hashlib.sha256(root + bytes.fromhex(node)).digest()).digest()
    return root


def build_header(job: dict, extranonce1: str, extranonce2: str, nonce: int) -> bytes:
    return (
        int(job["version"], 16).to_bytes(4, "little")
        + prevhash_to_header(job["prevhash"])
        + merkle_root(job["coinb1"], extranonce1, extranonce2, job["coinb2"],
                      job.get("merkle_branch", []))
        + int(job["ntime"], 16).to_bytes(4, "little")
        + int(job["nbits"], 16).to_bytes(4, "little")
        + nonce.to_bytes(4, "little")
    )


def meets(digest: bytes, target: int) -> bool:
    """Canonical comparison: the 256-bit number is the digest little-endian."""
    return int.from_bytes(digest, "little") <= target


class Session:
    """One pump task owns the socket; the flow consumes a queue. Nothing is lost mid-search."""

    def __init__(self, reader, writer, tx: Transcript) -> None:
        self.writer, self.tx = writer, tx
        self.queue: asyncio.Queue = asyncio.Queue()
        self.next_id = 0
        self.phase = "setup"
        self.pump = asyncio.create_task(self._pump(reader))

    async def _pump(self, reader) -> None:
        while True:
            line = await reader.readline()
            if not line:
                self.queue.put_nowait(None)
                return
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                self.queue.put_nowait(None)
                return
            method = message.get("method")
            if method == "mining.set_difficulty":
                self.tx.data["set_difficulty"].append(
                    {"value": message["params"][0], "phase": self.phase})
            elif method == "mining.notify":
                if self.phase == "search":
                    self.tx.data["stale_notifies"] = self.tx.data.get("stale_notifies", 0) + 1
                self.tx.data["jobs"].append(message["params"][0])
            self.queue.put_nowait(message)

    async def _next(self, timeout: float) -> dict:
        message = await asyncio.wait_for(self.queue.get(), timeout)
        if message is None:
            raise ConnectionError("pool closed the connection")
        return message

    async def send(self, method: str, params: list) -> int:
        self.next_id += 1
        self.writer.write((json.dumps(
            {"id": self.next_id, "method": method, "params": params}) + "\n").encode())
        await self.writer.drain()
        return self.next_id

    async def call(self, method: str, params: list, timeout: float) -> dict:
        wanted = await self.send(method, params)
        deadline = time.monotonic() + timeout
        while True:
            message = await self._next(max(0.01, deadline - time.monotonic()))
            if message.get("id") == wanted:
                return message

    async def wait_for(self, method: str, timeout: float) -> dict:
        deadline = time.monotonic() + timeout
        while True:
            message = await self._next(max(0.01, deadline - time.monotonic()))
            if message.get("method") == method:
                return message

    async def close(self) -> None:
        self.pump.cancel()
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except (ConnectionError, OSError):
            pass


async def smoke(args, tx: Transcript) -> int:
    raw_host = os.environ.get(args.host_var, "")
    host, port = endpoint(raw_host, args.port)
    use_tls = endpoint_scheme(raw_host) == "stratum+ssl"
    user = os.environ.get(args.user_var, "")
    password = os.environ.get(args.password_var, "x")
    tx.data["endpoint"] = f"{host}:{port}"
    tx.data["user"] = user
    if not user:
        tx.step("config", False, f"{args.user_var} is empty")
        return 4

    started = time.monotonic()
    try:
        ssl_ctx = ssl.create_default_context() if use_tls else None
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port, ssl=ssl_ctx,
                                    server_hostname=host if use_tls else None),
            args.timeout)
    except (OSError, asyncio.TimeoutError) as exc:
        tx.step("tcp_connect", False, f"{type(exc).__name__}: {exc}")
        return 3
    tx.step("tcp_connect", True,
            f"{(time.monotonic() - started) * 1000:.0f} ms" + (" (tls)" if use_tls else ""))

    session = Session(reader, writer, tx)
    try:
        if args.version_rolling:
            reply = await session.call(
                "mining.configure",
                [["version-rolling"], {"version-rolling.mask": "1fffe000"}], args.timeout)
            tx.step("configure", bool(reply.get("result")), json.dumps(reply.get("result")))

        reply = await session.call("mining.subscribe", [AGENT], args.timeout)
        result = reply.get("result")
        if not isinstance(result, list) or len(result) < 3:
            tx.step("subscribe", False, json.dumps(reply))
            return 2
        extranonce1, extranonce2_size = result[1], int(result[2])
        tx.step("subscribe", True, f"extranonce1={extranonce1} size={extranonce2_size}")

        reply = await session.call("mining.authorize", [user, password], args.timeout)
        if reply.get("result") is not True:
            tx.step("authorize", False, json.dumps(reply.get("error")))
            return 2
        tx.step("authorize", True, "accepted")

        session.phase = "wait_job"
        try:
            notify = await session.wait_for("mining.notify", args.job_timeout)
        except asyncio.TimeoutError:
            tx.step("job", False, f"no mining.notify within {args.job_timeout}s")
            return 2
        job = dict(zip(
            ("job_id", "prevhash", "coinb1", "coinb2", "merkle_branch", "version",
             "nbits", "ntime", "clean_jobs"), notify["params"]))
        tx.step("job", True, f"job_id={job['job_id']} clean={job['clean_jobs']}")

        if not args.submit_share:
            return 0

        difficulty = tx.data["set_difficulty"][-1]["value"] if tx.data["set_difficulty"] else None
        target = target_from_difficulty(difficulty) if difficulty else target_from_nbits(job["nbits"])
        tx.data.update({"difficulty": difficulty,
                        "target_source": "set_difficulty" if difficulty else "nbits",
                        "target_hex": f"{target:064x}"})
        extranonce2 = "00" * extranonce2_size
        tx.data["extranonce2"] = extranonce2

        session.phase = "search"
        deadline = time.monotonic() + args.share_seconds
        nonce, found = 0, None
        while time.monotonic() < deadline:
            digest = hashlib.sha256(
                hashlib.sha256(build_header(job, extranonce1, extranonce2, nonce)).digest()).digest()
            if meets(digest, target):
                found = nonce
                break
            nonce += 1
        tx.step("search", found is not None,
                f"nonce={found} hashes={nonce}" if found is not None
                else f"no share in {args.share_seconds}s ({nonce} hashes, target {tx.data['target_source']})")

        session.phase = "submit"
        submit_nonce = found if found is not None else 0
        header = build_header(job, extranonce1, extranonce2, submit_nonce)
        digest = hashlib.sha256(hashlib.sha256(header).digest()).digest()
        tx.data.update({"share_nonce": f"{submit_nonce:08x}",
                        "header_hex": header.hex(),
                        "share_hash_hex": digest[::-1].hex(),
                        "difficulty_events_during_search": sum(
                            1 for e in tx.data["set_difficulty"] if e["phase"] == "search"),
                        "stale_notifies": tx.data.get("stale_notifies", 0)})

        wanted = await session.send("mining.submit", [
            user, job["job_id"], extranonce2, job["ntime"], f"{submit_nonce:08x}"])
        reply = None
        deadline = time.monotonic() + args.timeout
        while time.monotonic() < deadline:
            message = await session._next(max(0.01, deadline - time.monotonic()))
            if message.get("id") == wanted:
                reply = message
                break
        accepted = bool(reply and reply.get("result") is True and reply.get("error") is None)
        tx.data["submits"].append({"reply": reply, "accepted": accepted})
        if reply is None:
            tx.step("submit", False, "no correlated reply")
            return 2
        if accepted:
            tx.step("submit", True, "accepted")
            return 0
        error = reply.get("error") or []
        framing = bool(error) and error[0] == LOW_DIFFICULTY
        tx.step("submit", framing, f"rejected: {error} (framing ok, not accepted)")
        if args.require_accept:
            return 2
        return 0 if framing else 2
    except (asyncio.TimeoutError, ConnectionError, KeyError, ValueError) as exc:
        tx.step("transport", False, f"{type(exc).__name__}: {exc}")
        return 2
    finally:
        await session.close()


def main() -> int:
    parser = Parser()
    parser.add_argument("--target", choices=sorted(PRESETS), default="braiins")
    parser.add_argument("--host-var", default="MINING_BRAIINS_HOST")
    parser.add_argument("--user-var", default="MINING_BRAIINS_USER")
    parser.add_argument("--password-var", default="MINING_BRAIINS_PASSWORD")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--job-timeout", type=float, default=45.0)
    parser.add_argument("--submit-share", action="store_true")
    parser.add_argument("--require-accept", action="store_true")
    parser.add_argument("--share-seconds", type=float, default=30.0)
    parser.add_argument("--version-rolling", action="store_true")
    args = parser.parse_args()

    if args.require_accept and not args.submit_share:
        parser.error("--require-accept requires --submit-share")

    if args.port is None:
        args.port = PRESETS[args.target][1]
    os.environ.setdefault(args.host_var, PRESETS[args.target][0])

    tx = Transcript(args.target)
    try:
        code = asyncio.run(smoke(args, tx))
    except ValueError as exc:
        tx.step("config", False, str(exc))
        code = 4
    except Exception as exc:  # malformed pool data must not escape as a traceback
        tx.step("unexpected", False, f"{type(exc).__name__}: {exc}")
        code = 2
    path = tx.write()
    for step in tx.data["steps"]:
        print(f"  [{'ok  ' if step['ok'] else 'FAIL'}] {step['step']}: {step['detail']}")
    print(f"transcript: {path}")
    return code


if __name__ == "__main__":
    sys.exit(main())

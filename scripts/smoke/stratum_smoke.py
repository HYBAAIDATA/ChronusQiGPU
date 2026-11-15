"""scripts/smoke/stratum_smoke.py — end-to-end Stratum V1 smoke.

Proves: TCP connect, subscribe, authorize, job receipt, and the submit/accept
round trip. Writes a transcript that doubles as a reproducible fixture
(job, extranonce1/2, target, nonce, header, digest).

Share search targets the SET_DIFFICULTY target (diff1 / difficulty), not nbits —
nbits is the network target and is harder than a pool share. At Bitcoin
difficulty 1 expect ~2^32 SHA-256d evaluations; use --search geometric|opencl
(Chronus structured search / QiGPU Mode A) or scale via fleet for wall-clock.
The schedule is a checked permutation over the nonce space — it raises
throughput when backed by QiGPU/OpenCL/fleet; it does not change the SHA-256d
oracle's expected trial count.

Exit 0 smoke passed, 2 protocol failure, 3 endpoint unreachable, 4 config error.
Against a live pool a submit usually returns error 23 "above target"; that is a
pass for framing, so exit 2 only on a malformed or uncorrelated reply. Add
--require-accept to demand a literal true (implies --submit-share).

    PYTHONPATH=src python scripts/smoke/stratum_smoke.py --target fake \\
        --submit-share --search geometric --share-seconds 600
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
_HEX = frozenset("0123456789abcdefABCDEF")
_TLS_SCHEMES = frozenset({"stratum+ssl", "stratum+tls", "ssl", "tls"})
_CLEAR_SCHEMES = frozenset({"stratum+tcp", "stratum", "tcp"})


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


def parse_host(host: str, port: int, scheme: str = "stratum+tcp") -> tuple[str, int, bool]:
    """Return (hostname, port, tls). Rejects unknown schemes; never silently drops TLS."""
    raw = host.strip()
    if not raw:
        raise ValueError("empty host")
    if "://" not in raw:
        raw = f"{scheme}://{raw}"
    parts = urlsplit(raw)
    if not parts.hostname:
        raise ValueError(f"no hostname in {host!r}")
    chosen = (parts.scheme or scheme).lower()
    if chosen in _TLS_SCHEMES:
        tls = True
    elif chosen in _CLEAR_SCHEMES:
        tls = False
    else:
        raise ValueError(f"unsupported scheme {chosen!r} in {host!r}")
    try:
        return parts.hostname, parts.port or port, tls
    except ValueError as exc:
        raise ValueError(f"bad port in {host!r}") from exc


# Back-compat alias used by older call sites / tests.
def endpoint(host: str, port: int, scheme: str = "stratum+tcp") -> tuple[str, int]:
    name, resolved_port, _tls = parse_host(host, port, scheme)
    return name, resolved_port


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


def _is_hex(text: object, length: int | None = None) -> bool:
    return (
        isinstance(text, str)
        and len(text) % 2 == 0
        and set(text) <= _HEX
        and (length is None or len(text) == length)
    )


def _resolve_search(name: str) -> str:
    if name != "auto":
        return name
    try:
        from chronus.execution.opencl_sha256d import OpenCLSha256dMinerBackend

        if OpenCLSha256dMinerBackend().is_available():
            return "opencl"
    except Exception:
        pass
    try:
        from chronus.execution.geometric_galois_miner import GeometricGaloisMiner  # noqa: F401

        return "geometric"
    except Exception:
        return "python"


async def search_share(
    backend: str,
    job: dict,
    extranonce1: str,
    extranonce2: str,
    target: int,
    deadline: float,
) -> tuple[int | None, int, str]:
    """Return (nonce_or_None, hashes_evaluated, backend_used).

    Runs each batch off the event loop so the Session pump can process
    set_difficulty / notify pushes during search.
    """
    backend = _resolve_search(backend)
    header76 = build_header(job, extranonce1, extranonce2, 0)[:76]
    hashes = 0
    loop = asyncio.get_running_loop()

    if backend == "opencl":
        from chronus.execution.opencl_sha256d import OpenCLSha256dMinerBackend

        miner = OpenCLSha256dMinerBackend()
        if not miner.is_available():
            raise RuntimeError(
                "OpenCL search requested but unavailable "
                "(set CHRONUS_ENABLE_OPENCL_MINER=1 on an OpenCL host)"
            )
        cursor = 0
        batch = 1 << 20
        while time.monotonic() < deadline and cursor < (1 << 32):
            width = min(batch, (1 << 32) - cursor)
            header80 = header76 + b"\x00\x00\x00\x00"
            hits = await loop.run_in_executor(
                None, miner.search, header80, cursor, cursor + width, target
            )
            hashes += width
            if hits:
                nonce = hits[0]
                digest = hashlib.sha256(
                    hashlib.sha256(header76 + nonce.to_bytes(4, "little")).digest()
                ).digest()
                if meets(digest, target):
                    return nonce, hashes, backend
            cursor += width
            await asyncio.sleep(0)
        return None, hashes, backend

    if backend == "geometric":
        from chronus.execution.geometric_galois_miner import GeometricGaloisMiner

        miner = GeometricGaloisMiner()
        cursor = 0
        batch = 1 << 16
        while time.monotonic() < deadline and cursor < (1 << 32):
            width = min(batch, (1 << 32) - cursor)
            result = await loop.run_in_executor(
                None, miner.solve_header_range, header76, target, cursor, width
            )
            hashes += result.iterations_evaluated
            if result.found and meets(result.header_hash, target):
                return result.nonce, hashes, backend
            cursor = (cursor + result.iterations_evaluated) % (1 << 32)
            if cursor == 0 and hashes >= (1 << 32):
                break
            await asyncio.sleep(0)
        return None, hashes, backend

    nonce = 0
    batch = 4096
    while time.monotonic() < deadline and nonce < (1 << 32):
        end = min(nonce + batch, 1 << 32)

        def _python_batch(start: int, stop: int) -> tuple[int | None, int]:
            for candidate in range(start, stop):
                digest = hashlib.sha256(
                    hashlib.sha256(header76 + candidate.to_bytes(4, "little")).digest()
                ).digest()
                if meets(digest, target):
                    return candidate, candidate - start + 1
            return None, stop - start

        found, stepped = await loop.run_in_executor(None, _python_batch, nonce, end)
        hashes += stepped
        if found is not None:
            return found, hashes, "python"
        nonce = end
        await asyncio.sleep(0)
    return None, hashes, "python"


class Session:
    """One pump task owns the socket; RPC replies and server pushes stay separated."""

    def __init__(self, reader, writer, tx: Transcript) -> None:
        self.writer, self.tx = writer, tx
        self.queue: asyncio.Queue = asyncio.Queue()
        self.stash: list[dict] = []
        self.next_id = 0
        self.phase = "setup"
        self.pump = asyncio.create_task(self._pump(reader))

    def _record_push(self, message: dict) -> None:
        method = message.get("method")
        params = message.get("params")
        if not isinstance(params, list):
            return
        if method == "mining.set_difficulty":
            if not params:
                return
            self.tx.data["set_difficulty"].append({"value": params[0], "phase": self.phase})
        elif method == "mining.notify":
            if not params:
                return
            if self.phase == "search":
                self.tx.data["stale_notifies"] = self.tx.data.get("stale_notifies", 0) + 1
            self.tx.data["jobs"].append(params[0])

    async def _pump(self, reader) -> None:
        reason = None
        try:
            while True:
                line = await reader.readline()
                if not line:
                    return
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    return
                if not isinstance(message, dict):
                    return
                try:
                    if message.get("method"):
                        self._record_push(message)
                except (TypeError, IndexError, KeyError):
                    pass
                self.queue.put_nowait(message)
        except Exception as exc:
            reason = exc
        finally:
            # Always wake waiters; include the failure reason when present.
            try:
                self.queue.put_nowait(None if reason is None else {"_pump_error": repr(reason)})
            except Exception:
                pass

    async def _next(self, timeout: float) -> dict:
        message = await asyncio.wait_for(self.queue.get(), timeout)
        if message is None:
            raise ConnectionError("pool closed the connection")
        if isinstance(message, dict) and "_pump_error" in message:
            raise ConnectionError(f"pool reader failed: {message['_pump_error']}")
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
            if message.get("method"):
                self.stash.append(message)

    async def wait_for(self, method: str, timeout: float) -> dict:
        for index, message in enumerate(self.stash):
            if message.get("method") == method:
                return self.stash.pop(index)
        deadline = time.monotonic() + timeout
        while True:
            message = await self._next(max(0.01, deadline - time.monotonic()))
            if message.get("method") == method:
                return message
            if message.get("method"):
                self.stash.append(message)

    async def close(self) -> None:
        self.pump.cancel()
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except (ConnectionError, OSError):
            pass


async def smoke(args, tx: Transcript) -> int:
    raw_host = os.environ.get(args.host_var, "")
    host, port, use_tls = parse_host(raw_host, args.port)
    user = os.environ.get(args.user_var, "")
    password = os.environ.get(args.password_var, "x")
    tx.data["endpoint"] = f"{'stratum+ssl' if use_tls else 'stratum+tcp'}://{host}:{port}"
    tx.data["user"] = user
    tx.data["tls"] = use_tls
    if not user:
        tx.step("config", False, f"{args.user_var} is empty")
        return 4

    started = time.monotonic()
    try:
        ssl_ctx = ssl.create_default_context() if use_tls else None
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(
                host, port, ssl=ssl_ctx, server_hostname=host if use_tls else None
            ),
            args.timeout,
        )
    except (OSError, asyncio.TimeoutError, ssl.SSLError) as exc:
        tx.step("tcp_connect", False, f"{type(exc).__name__}: {exc}")
        return 3
    tx.step(
        "tcp_connect",
        True,
        f"{(time.monotonic() - started) * 1000:.0f} ms" + (" (tls)" if use_tls else ""),
    )

    session = Session(reader, writer, tx)
    try:
        if args.version_rolling:
            reply = await session.call(
                "mining.configure",
                [["version-rolling"], {"version-rolling.mask": "1fffe000"}], args.timeout)
            tx.step("configure", bool(reply.get("result")), json.dumps(reply.get("result")))

        reply = await session.call("mining.subscribe", [AGENT], args.timeout)
        result = reply.get("result")
        if reply.get("error") or not isinstance(result, list) or len(result) < 3:
            tx.step("subscribe", False, json.dumps(reply))
            return 2
        extranonce1, extranonce2_size = result[1], result[2]
        if (
            not _is_hex(extranonce1)
            or type(extranonce2_size) is not int
            or isinstance(extranonce2_size, bool)
            or not 1 <= extranonce2_size <= 32
        ):
            tx.step("subscribe", False, f"unusable extranonce: {extranonce1!r} size={extranonce2_size!r}")
            return 2
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
        params = notify.get("params")
        if not isinstance(params, list) or len(params) < 9:
            tx.step("job", False, "malformed mining.notify")
            return 2
        job = dict(zip(
            ("job_id", "prevhash", "coinb1", "coinb2", "merkle_branch", "version",
             "nbits", "ntime", "clean_jobs"), params))
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
        jobs_before = len(tx.data["jobs"])
        diff_before = len(tx.data["set_difficulty"])
        deadline = time.monotonic() + args.share_seconds
        found, hashes, used = await search_share(
            args.search, job, extranonce1, extranonce2, target, deadline
        )
        tx.data["search_backend"] = used
        # Drain any pushes that arrived while the last batch ran.
        await asyncio.sleep(0)
        work_changed = len(tx.data["jobs"]) > jobs_before or any(
            e["phase"] == "search" for e in tx.data["set_difficulty"][diff_before:]
        )
        if work_changed and found is not None:
            # Refuse to submit the original job after an intervening notify/difficulty.
            detail = f"backend={used} hit nonce={found} but work changed mid-search ({hashes} hashes)"
            found = None
            tx.step("search", False, detail)
        elif found is not None:
            tx.step("search", True, f"backend={used} nonce={found} hashes={hashes}")
        else:
            tx.step(
                "search",
                False,
                f"backend={used} no share in {args.share_seconds}s "
                f"({hashes} hashes, target {tx.data['target_source']})",
            )

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
            if message.get("method"):
                session.stash.append(message)
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
    except (asyncio.TimeoutError, ConnectionError, KeyError, ValueError, RuntimeError) as exc:
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
    parser.add_argument(
        "--search",
        choices=("auto", "geometric", "opencl", "python"),
        default="auto",
        help="Share search backend: Chronus geometric/Galois, OpenCL QiGPU kernel, "
             "or pure-Python reference. auto prefers opencl then geometric.",
    )
    parser.add_argument("--version-rolling", action="store_true")
    args = parser.parse_args()

    if args.require_accept and not args.submit_share:
        parser.error("--require-accept requires --submit-share")

    if args.port is None:
        args.port = PRESETS[args.target][1]
    # --target fake must not inherit a live MINING_*_HOST; braiins may use env.
    if args.target == "fake":
        os.environ[args.host_var] = PRESETS["fake"][0]
    else:
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

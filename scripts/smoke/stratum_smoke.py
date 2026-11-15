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
import ipaddress
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
        base = f"{self.data['target']}-{self.stamp}"
        for suffix in range(0, 10_000):
            name = f"{base}.json" if suffix == 0 else f"{base}-{suffix}.json"
            path = EVIDENCE / name
            try:
                with path.open("x", encoding="utf-8") as handle:
                    handle.write(json.dumps(self.data, indent=2))
                return path
            except FileExistsError:
                continue
        raise RuntimeError(f"could not allocate a unique transcript under {EVIDENCE}")


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
    """Decode Bitcoin compact nBits into a positive 256-bit-or-smaller target.

    Rejects zero mantissa, the compact sign bit, and values that overflow a
    256-bit hash comparison (e.g. ``23000001`` → ``1 << 256``).
    """
    raw = int(nbits, 16)
    exponent = (raw >> 24) & 0xFF
    mantissa = raw & 0xFFFFFF
    if mantissa == 0:
        raise ValueError("nbits mantissa is zero")
    if mantissa & 0x00800000:
        raise ValueError("nbits sign bit is set")
    if exponent <= 3:
        target = mantissa >> (8 * (3 - exponent))
    else:
        shift = 8 * (exponent - 3)
        if shift >= 256 or mantissa.bit_length() + shift > 256:
            raise ValueError("nbits overflows a 256-bit target")
        target = mantissa << shift
    if target <= 0 or target.bit_length() > 256:
        raise ValueError("nbits is not a usable 256-bit target")
    return target


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


def validate_job_params(params: list) -> str | None:
    """Return a protocol error detail, or None when the notify is usable work."""
    if not isinstance(params, list) or len(params) < 9:
        return "mining.notify requires 9 params"
    job_id, prevhash, coinb1, coinb2, branches, version, nbits, ntime, clean = params[:9]
    if not isinstance(job_id, str) or not job_id:
        return "job_id must be a non-empty string"
    if not _is_hex(prevhash, 64):
        return "prevhash must be 64 hex characters"
    if not _is_hex(coinb1) or not _is_hex(coinb2):
        return "coinbase parts must be hex"
    if not isinstance(branches, list) or any(not _is_hex(branch, 64) for branch in branches):
        return "merkle branches must be 64-hex strings"
    if not _is_hex(version, 8) or not _is_hex(nbits, 8) or not _is_hex(ntime, 8):
        return "version, nbits and ntime must be 8 hex characters"
    if not isinstance(clean, bool):
        return "clean_jobs must be a boolean"
    try:
        target_from_nbits(nbits)
    except (ValueError, TypeError):
        return "nbits is not a usable compact target"
    return None


class WorkChanged(RuntimeError):
    """Pool issued clean_jobs=True and invalidated the selected job mid-search."""


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
    alive: asyncio.Event | None = None,
    work_generation: int | None = None,
    get_work_generation=None,
) -> tuple[int | None, int, str]:
    """Return (nonce_or_None, hashes_evaluated, backend_used).

    Runs each batch off the event loop so the Session pump can process
    set_difficulty / notify pushes during search. Stops when ``alive`` clears
    (pool disconnect) or the work generation advances (``clean_jobs=True``),
    instead of waiting out the share deadline.
    """
    backend = _resolve_search(backend)
    header76 = build_header(job, extranonce1, extranonce2, 0)[:76]
    hashes = 0
    loop = asyncio.get_running_loop()

    def _guards() -> None:
        if alive is not None and not alive.is_set():
            raise ConnectionError("pool closed during search")
        if (
            work_generation is not None
            and get_work_generation is not None
            and get_work_generation() != work_generation
        ):
            raise WorkChanged("pool replaced work during search")

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
            _guards()
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
        _guards()
        return None, hashes, backend

    if backend == "geometric":
        from chronus.execution.geometric_galois_miner import GeometricGaloisMiner

        miner = GeometricGaloisMiner()
        cursor = 0
        batch = 1 << 16
        while time.monotonic() < deadline and cursor < (1 << 32):
            _guards()
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
        _guards()
        return None, hashes, backend

    nonce = 0
    batch = 4096
    while time.monotonic() < deadline and nonce < (1 << 32):
        _guards()
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
    _guards()
    return None, hashes, "python"


class Session:
    """One pump task owns the socket; RPC replies and server pushes stay separated."""

    def __init__(self, reader, writer, tx: Transcript) -> None:
        self.writer, self.tx = writer, tx
        self.queue: asyncio.Queue = asyncio.Queue()
        self.stash: list[dict] = []
        self.next_id = 0
        self.phase = "setup"
        self.alive = asyncio.Event()
        self.alive.set()
        self.difficulty = None
        self.work_generation = 0
        self.pump = asyncio.create_task(self._pump(reader))

    def _record_push(self, message: dict) -> None:
        method = message.get("method")
        params = message.get("params")
        if not isinstance(params, list):
            return
        if method == "mining.set_difficulty":
            if not params:
                return
            # Applies to subsequent notifies; does not invalidate the selected job.
            self.difficulty = params[0]
            self.tx.data["set_difficulty"].append({"value": params[0], "phase": self.phase})
        elif method == "mining.notify":
            if not params:
                return
            # Difficulty in effect for this job is whatever arrived before this notify.
            message["_difficulty"] = self.difficulty
            clean = params[8] if len(params) > 8 else False
            # Only clean_jobs=True retires earlier jobs; non-clean leaves them valid.
            if clean is True:
                self.work_generation += 1
            message["_clean_jobs"] = clean is True
            message["_work_generation"] = self.work_generation
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
            self.alive.clear()
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
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise asyncio.TimeoutError()
            message = await self._next(remaining)
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
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise asyncio.TimeoutError()
            message = await self._next(remaining)
            if message.get("method") == method:
                return message
            if message.get("method"):
                self.stash.append(message)

    def take_pending(self, method: str) -> list[dict]:
        """Drain already-queued messages of ``method`` (stash + queue), preserving order."""
        taken: list[dict] = []
        kept: list[dict] = []
        for message in self.stash:
            if message.get("method") == method:
                taken.append(message)
            else:
                kept.append(message)
        self.stash = kept
        while True:
            try:
                message = self.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            if message is None:
                self.queue.put_nowait(None)
                break
            if isinstance(message, dict) and "_pump_error" in message:
                self.queue.put_nowait(message)
                break
            if isinstance(message, dict) and message.get("method") == method:
                taken.append(message)
            elif isinstance(message, dict) and message.get("method"):
                self.stash.append(message)
        return taken

    async def close(self) -> None:
        self.pump.cancel()
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except (ConnectionError, OSError):
            pass


def _hostname_looks_loopback(host: str) -> bool:
    return host.lower() in ("127.0.0.1", "localhost", "::1")


def _peer_is_loopback(writer) -> bool:
    """True when the connected peer address is a loopback IP (not a hostname spelling)."""
    peer = writer.get_extra_info("peername")
    if not peer:
        return False
    try:
        return ipaddress.ip_address(peer[0]).is_loopback
    except (TypeError, ValueError):
        return False


async def smoke(args, tx: Transcript) -> int:
    raw_host = os.environ.get(args.host_var, "")
    host, port, use_tls = parse_host(raw_host, args.port)
    user = os.environ.get(args.user_var, "")
    password = os.environ.get(args.password_var, "x")
    allow_cleartext = bool(getattr(args, "allow_cleartext", False))
    tx.data["endpoint"] = f"{'stratum+ssl' if use_tls else 'stratum+tcp'}://{host}:{port}"
    tx.data["user"] = user
    tx.data["tls"] = use_tls
    if not user:
        tx.step("config", False, f"{args.user_var} is empty")
        return 4
    # Fail fast for clearly remote cleartext hosts before opening a socket.
    if not use_tls and not _hostname_looks_loopback(host) and not allow_cleartext:
        tx.step(
            "config",
            False,
            "cleartext Stratum to a non-loopback host requires --allow-cleartext "
            "(worker credentials travel in the clear)",
        )
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

    peer_loopback = _peer_is_loopback(writer)
    tx.data["peer_loopback"] = peer_loopback
    if not use_tls and not peer_loopback and not allow_cleartext:
        # Hostname may say "localhost" while the resolver maps it elsewhere.
        try:
            writer.close()
            await writer.wait_closed()
        except (ConnectionError, OSError):
            pass
        tx.step(
            "config",
            False,
            "cleartext Stratum peer is not loopback; require --allow-cleartext "
            "(worker credentials travel in the clear)",
        )
        return 4
    if not use_tls and not peer_loopback:
        print(
            "warning: cleartext Stratum; use disposable worker credentials only",
            file=sys.stderr,
        )

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
        # Prefer the latest already-queued notify (e.g. clean_jobs replacement before auth ended).
        pending = session.take_pending("mining.notify")
        if pending:
            notify = pending[-1]
        params = notify.get("params")
        job_error = validate_job_params(params if isinstance(params, list) else [])
        if job_error is not None:
            tx.step("job", False, job_error)
            return 2
        job = dict(zip(
            ("job_id", "prevhash", "coinb1", "coinb2", "merkle_branch", "version",
             "nbits", "ntime", "clean_jobs"), params[:9]))
        # Difficulty snapshot attached when the notify was recorded (not a later push).
        job_difficulty = notify.get("_difficulty")
        job_work_generation = notify.get("_work_generation", session.work_generation)
        tx.data["selected_job"] = job
        tx.data["extranonce1"] = extranonce1
        tx.data["extranonce2_size"] = extranonce2_size
        tx.step(
            "job",
            True,
            f"job_id={job['job_id']} clean={job['clean_jobs']}"
            + (f" (selected latest of {1 + len(pending)})" if pending else ""),
        )

        if not args.submit_share:
            return 0

        if job_difficulty is not None:
            difficulty = job_difficulty
            target_source = "notify_difficulty"
        elif tx.data["set_difficulty"]:
            difficulty = tx.data["set_difficulty"][-1]["value"]
            target_source = "set_difficulty"
        else:
            difficulty = None
            target_source = "nbits"
        target = target_from_difficulty(difficulty) if difficulty else target_from_nbits(job["nbits"])
        tx.data.update({"difficulty": difficulty,
                        "target_source": target_source,
                        "target_hex": f"{target:064x}",
                        "work_generation": job_work_generation})
        extranonce2 = "00" * extranonce2_size
        tx.data["extranonce2"] = extranonce2

        session.phase = "search"
        deadline = time.monotonic() + args.share_seconds
        try:
            found, hashes, used = await search_share(
                args.search,
                job,
                extranonce1,
                extranonce2,
                target,
                deadline,
                alive=session.alive,
                work_generation=job_work_generation,
                get_work_generation=lambda: session.work_generation,
            )
        except WorkChanged as exc:
            tx.data["search_backend"] = _resolve_search(args.search)
            tx.data.update({
                "difficulty_events_during_search": sum(
                    1 for e in tx.data["set_difficulty"] if e["phase"] == "search"
                ),
                "stale_notifies": tx.data.get("stale_notifies", 0),
            })
            tx.step("search", False, f"{exc}")
            tx.step("submit", False, "skipped: work changed during search")
            return 2
        tx.data["search_backend"] = used
        # Drain any pushes that arrived while the last batch ran.
        await asyncio.sleep(0)
        # Only clean_jobs=True advances work_generation; set_difficulty and
        # non-clean notifies leave the selected job valid.
        work_changed = session.work_generation != job_work_generation
        tx.data.update({
            "difficulty_events_during_search": sum(
                1 for e in tx.data["set_difficulty"] if e["phase"] == "search"
            ),
            "stale_notifies": tx.data.get("stale_notifies", 0),
        })
        if work_changed:
            detail = (
                f"backend={used} clean_jobs invalidated mid-search "
                f"(hashes={hashes}, hit={found is not None})"
            )
            tx.step("search", False, detail)
            tx.step("submit", False, "skipped: work changed during search")
            return 2
        if found is None:
            tx.step(
                "search",
                False,
                f"backend={used} no share in {args.share_seconds}s "
                f"({hashes} hashes, target {tx.data['target_source']})",
            )
            if args.require_accept:
                tx.step("submit", False, "skipped: no share found")
                return 2
            # Framing path: submit nonce 0 only when work is still current.
        else:
            tx.step("search", True, f"backend={used} nonce={found} hashes={hashes}")

        session.phase = "submit"
        submit_nonce = found if found is not None else 0
        header = build_header(job, extranonce1, extranonce2, submit_nonce)
        digest = hashlib.sha256(hashlib.sha256(header).digest()).digest()
        tx.data.update({"share_nonce": f"{submit_nonce:08x}",
                        "header_hex": header.hex(),
                        "share_hash_hex": digest[::-1].hex()})

        wanted = await session.send("mining.submit", [
            user, job["job_id"], extranonce2, job["ntime"], f"{submit_nonce:08x}"])
        reply = None
        deadline = time.monotonic() + args.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            message = await session._next(remaining)
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
    parser.add_argument(
        "--allow-cleartext",
        action="store_true",
        help="Permit non-TLS Stratum to a non-loopback host (credentials travel in the clear).",
    )
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

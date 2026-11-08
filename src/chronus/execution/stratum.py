"""Stratum V1 mining-pool client and block-header assembly.

Clean-room implementation of the public Stratum V1 protocol (mining.subscribe,
mining.authorize, mining.notify, mining.set_difficulty, mining.submit) with
exact byte-order handling for Bitcoin header construction. Produces the same
80-byte headers the reference CPU miner (chronus.execution.mining) and the
OpenCL search kernel consume.

No external dependencies; transport is newline-delimited JSON over asyncio
streams, matching every public Stratum V1 pool.
"""

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Stratum difficulty-1 target: 0x00000000FFFF0000...0000 (2**208 * 0xFFFF).
DIFF1_TARGET = 0xFFFF << 208

_GENESIS_TARGET = DIFF1_TARGET  # Bitcoin's original nBits 0x1D00FFFF


class StratumError(RuntimeError):
    """Pool protocol error (transport failure or rejected RPC)."""


def sha256d(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def difficulty_to_target(difficulty: float) -> int:
    """Convert a pool difficulty to the 256-bit share target."""
    if not isinstance(difficulty, (int, float)) or difficulty <= 0:
        raise ValueError("difficulty must be a positive number")
    target = int(DIFF1_TARGET // difficulty)
    return min(target, (1 << 256) - 1)


def _le_word(hex_be: str) -> bytes:
    """Decode a 4-byte big-endian hex display word into header (LE) bytes."""
    raw = bytes.fromhex(hex_be)
    if len(raw) != 4:
        raise ValueError(f"expected 4-byte hex word, got {hex_be!r}")
    return raw[::-1]


def _swap_words(data: bytes) -> bytes:
    """Reverse each 4-byte word (stratum prevhash display -> header order)."""
    if len(data) % 4 != 0:
        raise ValueError("data length must be a multiple of 4 bytes")
    return b"".join(data[i : i + 4][::-1] for i in range(0, len(data), 4))


@dataclass(frozen=True)
class StratumJob:
    """One mining.notify work order."""

    job_id: str
    prevhash: str
    coinb1: str
    coinb2: str
    merkle_branch: Tuple[str, ...]
    version: str
    nbits: str
    ntime: str
    clean_jobs: bool = False

    @classmethod
    def from_notify(cls, params: List[Any]) -> "StratumJob":
        if len(params) != 9:
            raise ValueError("mining.notify must carry 9 parameters")
        (
            job_id,
            prevhash,
            coinb1,
            coinb2,
            merkle_branch,
            version,
            nbits,
            ntime,
            clean_jobs,
        ) = params
        return cls(
            job_id=str(job_id),
            prevhash=str(prevhash),
            coinb1=str(coinb1),
            coinb2=str(coinb2),
            merkle_branch=tuple(str(b) for b in merkle_branch),
            version=str(version),
            nbits=str(nbits),
            ntime=str(ntime),
            clean_jobs=bool(clean_jobs),
        )


@dataclass(frozen=True)
class StratumSession:
    """Subscription state returned after the subscribe handshake."""

    extranonce1: bytes
    extranonce2_size: int
    difficulty: float = 1.0

    @property
    def target(self) -> int:
        return difficulty_to_target(self.difficulty)


def build_coinbase(job: StratumJob, extranonce2: bytes, session: StratumSession) -> bytes:
    """Assemble the full coinbase transaction for a share attempt."""
    if len(extranonce2) != session.extranonce2_size:
        raise ValueError(
            f"extranonce2 must be exactly {session.extranonce2_size} bytes"
        )
    return (
        bytes.fromhex(job.coinb1)
        + session.extranonce1
        + extranonce2
        + bytes.fromhex(job.coinb2)
    )


def merkle_root(coinbase_hash: bytes, branch: Tuple[str, ...]) -> bytes:
    """Fold the coinbase hash through the merkle branch (internal byte order)."""
    node = coinbase_hash
    for step in branch:
        node = sha256d(node + bytes.fromhex(step))
    return node


def build_header_prefix(
    job: StratumJob, extranonce2: bytes, session: StratumSession
) -> bytes:
    """Build the 76-byte header prefix; the final 4 bytes are the LE nonce."""
    coinbase = build_coinbase(job, extranonce2, session)
    root = merkle_root(sha256d(coinbase), job.merkle_branch)
    prevhash_raw = bytes.fromhex(job.prevhash)
    if len(prevhash_raw) != 32:
        raise ValueError("prevhash must be 32 bytes")
    prefix = (
        _le_word(job.version)
        + _swap_words(prevhash_raw)
        + root
        + _le_word(job.ntime)
        + _le_word(job.nbits)
    )
    if len(prefix) != 76:
        raise AssertionError("header prefix must be 76 bytes")
    return prefix


def build_header(
    job: StratumJob, extranonce2: bytes, session: StratumSession, nonce: int
) -> bytes:
    """Full 80-byte header for a candidate nonce."""
    if not 0 <= nonce < 1 << 32:
        raise ValueError("nonce must be a 32-bit unsigned integer")
    return build_header_prefix(job, extranonce2, session) + nonce.to_bytes(4, "little")


@dataclass
class _Event:
    kind: str  # "job" | "difficulty" | "response"
    job: Optional[StratumJob] = None
    difficulty: Optional[float] = None
    response: Optional[Dict[str, Any]] = None


class StratumV1Client:
    """Async Stratum V1 pool client.

    Usage::

        client = StratumV1Client("pool.example.com", 3333, "user.worker", "x")
        session = await client.connect()
        job = await client.next_job()
        header = build_header(job, en2, session, nonce)
        accepted = await client.submit(job, en2, nonce)
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        user_agent: str = "chronus-igpu/36.0.1",
    ) -> None:
        if not host or not isinstance(host, str):
            raise ValueError("host must be a non-empty string")
        if not 1 <= port <= 65535:
            raise ValueError("port must be in [1, 65535]")
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.user_agent = user_agent
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._next_id = 1
        self._pending: Dict[int, Any] = {}
        self._events: asyncio.Queue[_Event] = asyncio.Queue()
        self._pump_task: Optional[asyncio.Task] = None
        self._difficulty = 1.0

    async def connect(self) -> StratumSession:
        """Open the connection and complete subscribe + authorize."""
        self._reader, self._writer = await asyncio.open_connection(
            self.host, self.port
        )
        self._pump_task = asyncio.create_task(self._pump())

        subscribe_result = await self._rpc("mining.subscribe", [self.user_agent])
        # Result: [[["mining.set_difficulty", subid], ["mining.notify", subid]],
        #          extranonce1_hex, extranonce2_size]
        extranonce1_hex = subscribe_result[1]
        extranonce2_size = int(subscribe_result[2])
        session = StratumSession(
            extranonce1=bytes.fromhex(extranonce1_hex),
            extranonce2_size=extranonce2_size,
        )

        authorized = await self._rpc(
            "mining.authorize", [self.username, self.password]
        )
        if authorized is not True:
            await self.close()
            raise StratumError("pool rejected mining.authorize")
        return session

    async def _rpc(self, method: str, params: List[Any]) -> Any:
        request_id = self._next_id
        self._next_id += 1
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        # Register before writing: a fast pool may answer before we await.
        self._pending[request_id] = future
        message = {"id": request_id, "method": method, "params": params}
        assert self._writer is not None
        self._writer.write((json.dumps(message) + "\n").encode("utf-8"))
        await self._writer.drain()
        response = await future
        if response.get("error"):
            raise StratumError(f"{method} rejected: {response['error']}")
        return response.get("result")

    async def _pump(self) -> None:
        assert self._reader is not None
        try:
            while True:
                line = await self._reader.readline()
                if not line:
                    await self._events.put(
                        _Event("response", response={"error": "pool disconnected"})
                    )
                    return
                try:
                    message = json.loads(line.decode("utf-8").strip())
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue  # ignore malformed pool chatter
                if "method" in message:
                    method = message.get("method")
                    params = message.get("params", [])
                    if method == "mining.notify":
                        await self._events.put(
                            _Event("job", job=StratumJob.from_notify(params))
                        )
                    elif method == "mining.set_difficulty" and params:
                        diff_val = (params[0] + 0.0) if isinstance(params[0], (int, float)) else 1.0
                        await self._events.put(
                            _Event("difficulty", difficulty=diff_val)
                        )
                else:
                    request_id = message.get("id")
                    future = self._pending.pop(request_id, None)
                    if future is not None and not future.done():
                        future.set_result(message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # transport failure surfaces to waiters
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(StratumError(str(exc)))
            self._pending.clear()

    async def next_job(self) -> Tuple[StratumJob, float]:
        """Wait for the next job, tracking difficulty changes. Returns (job, difficulty)."""
        while True:
            event = await self._events.get()
            if event.kind == "job" and event.job is not None:
                return event.job, self._difficulty
            if event.kind == "difficulty" and event.difficulty is not None:
                self._difficulty = event.difficulty
            if event.kind == "response" and event.response and event.response.get("error"):
                raise StratumError(str(event.response["error"]))

    async def submit(
        self,
        job: StratumJob,
        extranonce2: bytes,
        nonce: int,
        ntime: Optional[str] = None,
    ) -> bool:
        """Submit a share; returns True if the pool accepted it."""
        result = await self._rpc(
            "mining.submit",
            [
                self.username,
                job.job_id,
                extranonce2.hex(),
                ntime or job.ntime,
                f"{nonce:08x}",
            ],
        )
        return result is True

    async def close(self) -> None:
        # Close the transport before cancelling the pump: cancelling a task
        # blocked in StreamReader.readline() can leave the transport in a
        # state where the peer never observes EOF.
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
        if self._pump_task is not None:
            self._pump_task.cancel()
            try:
                await self._pump_task
            except (asyncio.CancelledError, Exception):
                pass
            self._pump_task = None

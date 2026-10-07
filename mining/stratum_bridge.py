"""Python Stratum V1 bridge: TCP subscribe/authorize/notify/submit.

CANONICITY: this is a LEGACY bridge — a second Stratum client for the HYBA
hash-pipeline harness and its tests. It is NOT the canonical production
mining path and owns no live mining state. The canonical path is
``chronus.mla1517.mining.coordinator`` (epochs, leases, dispatch
certificates, submission lifecycle) driven by
``chronus/mla1517_platform/python/mining_runtime.py`` (``--mine``).
Do not add new production callers here.

Ports the proven `src/lib/stratum_tcp_client.ts` protocol to Python so the
Python hash pipeline (mining/hash_pipeline.py) can close the P0 gate:
shares_accepted > 0 on testnet BEFORE mainnet (workflow pdf section 1, 7).

Triple-gate for live submit (mirrors TS isLiveSubmitApproved):
  HYBA_ENABLE_LIVE_SHARE_SUBMIT=true + HYBA_LIVE_SHARE_APPROVAL_ID set
  + HYBA_AUTONOMOUS_EXTERNAL_ACTIONS=true. Otherwise --dry-run only.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import ipaddress
import json
import math
import os
import sys
import time
import threading
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, List, Optional

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def load_env_file(dotenv_path: Optional[str] = None) -> None:
    if dotenv_path is None:
        dotenv_path = os.path.join(_PROJECT_ROOT, ".env")
    if not os.path.isfile(dotenv_path):
        return
    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


# NOTE: .env is loaded in main(), not at import time — importing this module
# as a library (e.g. hash_pipeline's lane-order delegation, test suites)
# must not mutate os.environ.

try:
    from mining.hash_pipeline import HashPipeline, double_sha256
except ImportError:
    try:
        from hash_pipeline import HashPipeline, double_sha256
    except ImportError:
        HashPipeline = None  # type: ignore[assignment]
        double_sha256 = None  # type: ignore[assignment]


def is_live_submit_approved(env=None) -> bool:
    e = env if env is not None else os.environ
    return (
        e.get("HYBA_ENABLE_LIVE_SHARE_SUBMIT") == "true"
        and bool(e.get("HYBA_LIVE_SHARE_APPROVAL_ID"))
        and e.get("HYBA_AUTONOMOUS_EXTERNAL_ACTIONS") == "true"
    )


def _runtime_config_path() -> str:
    override = os.environ.get("PYTHIA_RUNTIME_CONFIG", "").strip()
    if override:
        return override
    return os.path.join(_PROJECT_ROOT, "data", "runtime_config.json")


def _load_runtime_config() -> dict:
    """Read the operator's runtime config (written only by the control
    API's /config endpoint). Missing or malformed files yield {} — every
    downstream check treats that as 'not configured'."""
    try:
        with open(_runtime_config_path(), "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _config_live_submit_permits(host: str, port: int, worker: str) -> bool:
    """Config-side live gate, polled per submit attempt.

    The operator enables live submit through the control API, which writes
    approval_id = sha256(endpoint|worker). Submit is permitted only when
    the arm's actual connection identity matches the approval exactly —
    a pool change without a fresh enable mismatches and the gate closes.
    """
    cfg = _load_runtime_config()
    live = cfg.get("live_submit") or {}
    approval = live.get("approval_id") or ""
    if not live.get("enabled") or len(approval) != 64:
        return False
    pool = next((p for p in cfg.get("pools", []) if p.get("enabled")), None)
    if pool is None:
        return False
    endpoint = f"{host}:{port}"
    if pool.get("endpoint") != endpoint or pool.get("worker") != worker:
        return False
    return hashlib.sha256(f"{endpoint}|{worker}".encode("utf-8")).hexdigest() == approval


def _configured_target_hs() -> float:
    """Operator target hashrate from the runtime config (H/s).

    0 means 'run at the device's physical rate'. Any positive value paces
    window grinding to that rate; writes above the governed ceiling
    (10 EH/s) are rejected at the API, so this reader only defends against
    a manually edited file."""
    cfg = _load_runtime_config()
    try:
        target = float((cfg.get("hashrate") or {}).get("target_hs", 0.0))
    except (TypeError, ValueError):
        return 0.0
    if not 0.0 <= target <= 1e19:  # mirrors runtime_config.HASHRATE_CEILING_HS
        return 0.0
    return target


_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")


def _is_hex(value, length: Optional[int] = None) -> bool:
    """Strict hex-field check: exact length when given, even length, hex only.

    ``bytes.fromhex`` alone is not enough: it silently skips whitespace, so a
    short/whitespace-padded pool field would decode to fewer bytes than the
    fixed-width header slot it lands in. A pool is an untrusted peer — every
    field is checked at ingestion, never trusted by shape.
    """
    if not isinstance(value, str):
        return False
    if length is not None and len(value) != length:
        return False
    if len(value) % 2:
        return False
    return all(ch in _HEX_DIGITS for ch in value)


def _check_hex(value, length: Optional[int], name: str) -> str:
    if not _is_hex(value, length):
        raise ValueError(f"malformed {name}: {value!r}")
    return value


def _validate_notify_params(params: list) -> dict:
    """Wire-validate one mining.notify parameter vector.

    Any malformed field rejects the whole notify: a pool that cannot even
    frame a job correctly cannot be mined against, and a half-parsed job
    would die later inside ``mine_job`` — after the listener already cached
    it. Raises ValueError naming the bad field.
    """
    branch = params[4]
    if not isinstance(branch, (list, tuple)):
        raise ValueError("malformed merkle_branch: not a list")
    return {
        "job_id": str(params[0]),
        "prev_hash": _check_hex(params[1], 64, "prev_hash"),
        "coinb1": _check_hex(params[2], None, "coinb1"),
        "coinb2": _check_hex(params[3], None, "coinb2"),
        "merkle_branch": [_check_hex(x, 64, "merkle_branch") for x in branch],
        "version": _check_hex(params[5], 8, "version"),
        "nbits": _check_hex(params[6], 8, "nbits"),
        "ntime": _check_hex(params[7], 8, "ntime"),
        "clean_jobs": bool(params[8]),
    }


def difficulty_to_target(difficulty: float) -> int:
    """floor(DIFF1_TARGET / difficulty) as an exact rational.

    The pool-announced difficulty is parsed through ``str()`` so the
    Fraction sees the decimal value the pool sent — never the binary
    float64 expansion, and never a 28-digit context-precision quotient.
    The 1e-12 floor matches the previous clamp semantics.
    """
    diff1 = 0x00000000FFFF0000000000000000000000000000000000000000000000000000
    d = max(Fraction(str(difficulty)), Fraction(1, 10**12))
    target = Fraction(diff1, 1) / d
    return target.numerator // target.denominator


@dataclass
class LiveJob:
    job_id: str = ""
    prev_hash: str = ""
    coinb1: str = ""
    coinb2: str = ""
    merkle_branch: List[str] = field(default_factory=list)
    version: str = ""
    nbits: str = ""
    ntime: str = ""
    clean_jobs: bool = False
    difficulty: float = 1.0


class StratumBridge:
    """Asyncio Stratum V1 client. Acceptance ONLY on result:true.

    Transport is a single asyncio stream pair. ``listen_forever()`` owns
    the read loop once running; ``_rpc`` resolves pool responses through a
    pending-request table so submissions get verdicts while job notify
    messages keep flowing through ``_handle_server_message``.
    """

    def __init__(
        self,
        host: str,
        port: int,
        worker: Optional[str] = None,
        password: Optional[str] = None,
        agent: str = "PYTHIA/2.0",
        *,
        worker_name: Optional[str] = None,
        worker_pass: Optional[str] = None,
    ) -> None:
        self.host = host
        self.port = port
        self.worker = worker_name if worker_name is not None else worker
        self.password = worker_pass if worker_pass is not None else password
        self.agent = agent
        # Legacy attribute: asyncio transport uses streams, never a socket.
        self.sock = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._id = 1
        self._pending: Dict[int, tuple] = {}
        self._listening = False
        self.connected = False
        self.authorized = False
        self.extranonce1 = ""
        self.extranonce2_size = 4
        self.difficulty = 1.0
        self.last_job: Optional[LiveJob] = None
        self.clean_job_generation = 0
        self.shares_accepted = 0
        self.shares_rejected = 0
        self.submit_calls = 0
        # Count of pool messages dropped for malformed wire fields.
        self.malformed_messages = 0
        self._accounting_lock = threading.Lock()
        # Measured socket flush time of the most recent RPC (ms). This is
        # the dispatch invariant (<1.5ms) - verdict round-trip latency is
        # measured separately at the call site.
        self.last_dispatch_ms: Optional[float] = None

    # -- transport ------------------------------------------------------

    async def connect(self, timeout: float = 5.0) -> None:
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port), timeout
        )
        self.connected = True

    async def handshake(self, suggest_diff: Optional[float] = None) -> None:
        result = await self._rpc("mining.subscribe", [self.agent])
        if isinstance(result, list) and len(result) >= 3:
            # extranonce1/extranonce2_size feed every coinbase build; a
            # malformed pair makes every job unmineable, so the handshake
            # fails closed here rather than once per notify inside mine_job.
            extranonce1 = str(result[1])
            if not _is_hex(extranonce1):
                raise RuntimeError(
                    f"malformed extranonce1 in mining.subscribe: {extranonce1!r}"
                )
            try:
                extranonce2_size = int(result[2])
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"malformed extranonce2_size in mining.subscribe: {result[2]!r}"
                ) from exc
            if not 0 < extranonce2_size <= 32:
                raise RuntimeError(
                    f"malformed extranonce2_size in mining.subscribe: {result[2]!r}"
                )
            self.extranonce1 = extranonce1
            self.extranonce2_size = extranonce2_size
        if suggest_diff is not None:
            try:
                await self._rpc("mining.suggest_difficulty", [suggest_diff], timeout=3.0)
            except Exception:
                pass
        auth = await self._rpc("mining.authorize", [self.worker, self.password])
        self.authorized = auth is True
        if not self.authorized:
            raise RuntimeError("mining.authorize rejected")

    async def _rpc(self, method: str, params: list, timeout: float = 8.0):
        assert self._writer is not None
        pid = self._id
        self._id += 1
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._pending[pid] = (method, fut)
        t0 = time.perf_counter()
        self._writer.write(
            (json.dumps({"id": pid, "method": method, "params": params}) + "\n").encode("utf-8")
        )
        await self._writer.drain()
        self.last_dispatch_ms = (time.perf_counter() - t0) * 1000.0
        if self._listening:
            try:
                return await asyncio.wait_for(fut, timeout)
            finally:
                # Bounded pending table: a timed-out RPC must not leak its
                # entry. A late response then falls through the server-
                # message path harmlessly (no method name).
                self._pending.pop(pid, None)
        # No listen loop yet (handshake): read inline until our response.
        deadline = loop.time() + timeout
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                self._pending.pop(pid, None)
                raise TimeoutError(f"{method} timeout")
            line = await asyncio.wait_for(self._reader.readline(), remaining)
            if not line:
                self._pending.pop(pid, None)
                raise ConnectionError("pool closed connection")
            try:
                parsed = json.loads(line.decode("utf-8").strip())
            except json.JSONDecodeError:
                continue
            self._dispatch(parsed)
            if fut.done():
                return fut.result()

    def _dispatch(self, parsed: dict) -> None:
        """Route a server message: pending RPC response or job notify."""
        pid = parsed.get("id")
        entry = self._pending.pop(pid, None) if pid is not None else None
        if entry is not None:
            method, fut = entry
            if parsed.get("error"):
                fut.set_exception(RuntimeError(f"{method} error: {parsed['error']}"))
            else:
                fut.set_result(parsed.get("result"))
            return
        self._handle_server_message(parsed)

    async def listen_forever(self) -> None:
        """Own the socket read loop; resolves RPCs and caches job notify."""
        if self._reader is None:
            raise RuntimeError("not connected")
        self._listening = True
        try:
            while True:
                try:
                    line = await self._reader.readline()
                except (
                    ConnectionError,
                    ConnectionResetError,
                    OSError,
                    asyncio.TimeoutError,
                    asyncio.LimitOverrunError,
                ):
                    # LimitOverrunError joins the transport-failure family:
                    # an oversized line means the stream cannot be framed
                    # again, so the listener exits cleanly — pending RPCs
                    # get ConnectionError in the finally, not an orphaned
                    # task exception that leaves the miner grinding blind.
                    break
                if not line:
                    break
                try:
                    parsed = json.loads(line.decode("utf-8").strip())
                except json.JSONDecodeError:
                    continue
                self._dispatch(parsed)
        finally:
            self._listening = False
            for _, (method, fut) in self._pending.items():
                if not fut.done():
                    fut.set_exception(ConnectionError("listener stopped"))
            self._pending.clear()

    def _handle_server_message(self, parsed: dict) -> None:
        method = parsed.get("method")
        params = parsed.get("params", [])
        if method == "mining.set_difficulty":
            # A non-numeric or non-finite difficulty must not poison the
            # cached job or kill the listener — it is dropped and counted.
            first = params[0] if isinstance(params, (list, tuple)) and params else None
            try:
                difficulty = float(first)
            except (TypeError, ValueError):
                difficulty = None
            if difficulty is None or not math.isfinite(difficulty) or difficulty <= 0:
                self.malformed_messages += 1
            else:
                self.difficulty = difficulty
                if self.last_job is not None:
                    self.last_job.difficulty = self.difficulty
        elif method == "mining.notify" and isinstance(params, list):
            if len(params) >= 9:
                try:
                    fields = _validate_notify_params(params)
                except (ValueError, IndexError):
                    self.malformed_messages += 1
                    print("[BAD NOTIFY] dropped malformed mining.notify from pool")
                else:
                    if fields["clean_jobs"]:
                        self.clean_job_generation += 1
                    self.last_job = LiveJob(
                        difficulty=self.difficulty,
                        **fields,
                    )

    def is_job_valid(self, clean_job_generation: int) -> bool:
        return clean_job_generation == self.clean_job_generation

    async def wait_for_job(self, timeout: float = 30.0) -> LiveJob:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.last_job is not None and self.last_job.job_id:
                return self.last_job
            if self._listening:
                await asyncio.sleep(0.05)
                continue
            # The deadline holds while reading too: a silent pool must not
            # hold this call past its timeout.
            try:
                line = await asyncio.wait_for(
                    self._reader.readline(), max(0.0, deadline - time.time())
                )
            except asyncio.TimeoutError:
                break
            if not line:
                raise ConnectionError("pool closed connection")
            try:
                parsed = json.loads(line.decode("utf-8").strip())
            except json.JSONDecodeError:
                continue
            self._dispatch(parsed)
        raise TimeoutError("no mining.notify received")

    def get_active_job(self) -> Optional[dict]:
        """The cached mining.notify template, or None."""
        j = self.last_job
        if j is None:
            return None
        return {
            "job_id": j.job_id,
            "prevhash": j.prev_hash,
            "coinb1": j.coinb1,
            "coinb2": j.coinb2,
            "merkle_branch": list(j.merkle_branch),
            "version": j.version,
            "nbits": j.nbits,
            "ntime": j.ntime,
            "clean_jobs": j.clean_jobs,
            "difficulty": j.difficulty,
        }

    # -- submission -----------------------------------------------------

    def _submit_permitted(self) -> bool:
        """Fail-closed gate: env approval, OR a runtime-config approval
        bound to this connection identity, OR an active session bound to
        a loopback test pool (no real-world side effect)."""
        if is_live_submit_approved():
            return True
        if _config_live_submit_permits(self.host, self.port, self.worker):
            return True
        if self._writer is not None:
            try:
                if ipaddress.ip_address(self.host).is_loopback:
                    return True
            except ValueError:
                return self.host in ("localhost",)
        return False

    def submit_share(
        self,
        job_id: str,
        extranonce2: str,
        ntime: str,
        nonce: Optional[str] = None,
        *,
        nonce_hex: Optional[str] = None,
    ):
        """Sync-callable gate: returns None when submission is not
        permitted (no socket I/O occurs). When permitted, returns the
        ``_submit_async`` coroutine to await."""
        nonce = nonce if nonce is not None else nonce_hex
        if not self._submit_permitted():
            return None
        if not self.connected or not self.authorized:
            raise RuntimeError("not connected/authorized")
        return self._submit_async(job_id, extranonce2, ntime, nonce)

    async def _submit_async(self, job_id: str, extranonce2: str, ntime: str, nonce: str) -> bool:
        with self._accounting_lock:
            self.submit_calls += 1
        result = await self._rpc("mining.submit", [self.worker, job_id, extranonce2, ntime, nonce])
        accepted = result is True
        with self._accounting_lock:
            if accepted:
                self.shares_accepted += 1
            else:
                self.shares_rejected += 1
        return accepted

    async def disconnect(self) -> None:
        writer, self._writer = self._writer, None
        self._reader = None
        self.connected = False
        self.authorized = False
        if writer is not None:
            writer.close()
            try:
                # A peer that never acknowledges the close must not hold us.
                await asyncio.wait_for(writer.wait_closed(), 5.0)
            except asyncio.TimeoutError:
                writer.transport.abort()
            except Exception:
                pass

    def close(self) -> None:
        """Sync close: drops the writer without awaiting it."""
        if self._writer is not None:
            self._writer.close()
        self._writer = None
        self._reader = None
        self.connected = False
        self.authorized = False


def build_coinbase(
    coinb1_hex: str, extranonce1_hex: str, extranonce2_hex: str, coinb2_hex: str
) -> bytes:
    """Assemble coinbase tx: coinb1 + extranonce1 + extranonce2 + coinb2."""
    return bytes.fromhex(coinb1_hex + extranonce1_hex + extranonce2_hex + coinb2_hex)


def coinbase_hash(coinbase: bytes) -> bytes:
    if double_sha256 is not None:
        return double_sha256(coinbase)
    return hashlib.sha256(hashlib.sha256(coinbase).digest()).digest()


def merkle_root(coinbase_tx_hash: bytes, branch_hexes: list) -> bytes:
    """Fold coinbase hash up the branch path with double-SHA256."""
    dsha = (
        double_sha256
        if double_sha256 is not None
        else (lambda b: hashlib.sha256(hashlib.sha256(b).digest()).digest())
    )
    curr = coinbase_tx_hash
    for branch_hex in branch_hexes:
        curr = dsha(curr + bytes.fromhex(branch_hex))
    return curr


def build_header80(
    version_hex: str, prev_hash_hex: str, merkle_root_hex: str, ntime_hex: str, nbits_hex: str
) -> bytes:
    """Assemble the 80-byte header template (nonce field zeroed).

    Stratum hexes are big-endian display; header fields are little-endian.
    prev_hash arrives grouped in 4-byte LE words (swab per word).
    """

    def le(hex8: str) -> bytes:
        return bytes.fromhex(hex8)[::-1]

    header = bytearray(80)
    header[0:4] = le(version_hex[-8:])
    # prev_hash: reverse each 4-byte word group, then place.
    prev = bytes.fromhex(prev_hash_hex[-64:])
    words = [prev[i : i + 4][::-1] for i in range(0, 32, 4)]
    header[4:36] = b"".join(words)
    header[36:68] = bytes.fromhex(merkle_root_hex[-64:])[::-1]
    header[68:72] = le(ntime_hex[-8:])
    header[72:76] = le(nbits_hex[-8:])
    header[76:80] = b"\x00\x00\x00\x00"
    return bytes(header)


def nonce_order_name(order: Optional[str] = None) -> str:
    """The configured nonce traversal order (``order`` overrides the env)."""
    return (order or os.environ.get("PYTHIA_NONCE_ORDER", "m32")).lower()


def _linear_nonces(base_nonce: int, count: int) -> List[int]:
    return [(base_nonce + i) & 0xFFFFFFFF for i in range(count)]


def _lucas15_schedule_nonces(base_nonce: int, count: int) -> List[int]:
    """Coverage-complete Lucas-15 schedule-only ablation arm.

    ``M^15 = [[987, 610], [610, 377]]`` and ``trace(M^15) = 1364``.  The
    first coefficient coprime to the current window defines an affine
    permutation.  This changes candidate order only; SHA-256d remains the
    protocol acceptance authority and no quantum speedup is claimed.
    """
    if count <= 0:
        return []
    for candidate in (987, 610, 377, 1364):
        stride = candidate % count or 1
        if math.gcd(stride, count) == 1:
            break
    else:
        stride = 1
        while math.gcd(stride, count) != 1:
            stride += 2
    offset = 610 % count
    return [
        (base_nonce + ((offset + i * stride) % count)) & 0xFFFFFFFF
        for i in range(count)
    ]


def _poincare_11d_nonces(
    base_nonce: int, count: int, header80: Optional[bytes]
) -> Optional[List[int]]:
    """Coverage-complete 11D shard order over [base_nonce, base_nonce+count).

    The header's 76-byte prefix is folded into the 11D Poincaré-golden
    ball; the folded vector ranks the 32-face dual compass by golden-metric
    affinity; each face's shard is then walked by a Cassini-certified
    affine permutation whose stride is coprime to the shard width — a
    bijection, so every nonce in the window is emitted exactly once
    (Intelligence/search_crystal.py). Returns None when the engine is not
    importable, so callers fall back rather than silently reorder."""
    try:
        from Intelligence.search_crystal import PoincareCassiniSearchEngine
    except Exception:
        return None
    engine = PoincareCassiniSearchEngine(total_nonce_space=count, nonce_start=base_nonce)
    prefix = bytes(header80[:76]) if header80 is not None else b"\x00" * 76
    return engine.enumerate_nonces(prefix)


def _lane_nonces(
    base_nonce: int,
    count: int,
    header80: Optional[bytes] = None,
    order: Optional[str] = None,
) -> List[int]:
    """Enumerate `count` nonces in the configured traversal order.

    PYTHIA_NONCE_ORDER (or the ``order`` argument) selects the order:
      linear/flat — base + i; the counterfactual control arm.
      lucas15/operator — a coverage-complete affine permutation derived from
          the exact M^15 coefficients; schedule-only experimental arm.
      11d/poincare11d/manifold — Poincaré–Cassini 11D shard order driven
          by header80 (defaults to a zero header when not supplied).
      m32 (default) — the canonical solver's equal partition across the
          32 lanes (nonce = base + lane + LANES*epoch).
    Every arm covers the same window exactly once; only ordering differs.
    Unavailable engines fall back to linear order."""
    mode = nonce_order_name(order)
    if mode in ("linear", "flat"):
        return _linear_nonces(base_nonce, count)
    if mode in ("lucas15", "lucas_15", "operator"):
        return _lucas15_schedule_nonces(base_nonce, count)
    if mode in ("11d", "poincare11d", "poincare", "manifold"):
        nonces = _poincare_11d_nonces(base_nonce, count, header80)
        return nonces if nonces is not None else _linear_nonces(base_nonce, count)
    platform_py = os.path.join(_PROJECT_ROOT, "chronus/mla1517_platform", "python")
    try:
        if platform_py not in sys.path:
            sys.path.append(platform_py)
        from chronus.mla1517.mining.solver import M32SearchSolver

        solver = M32SearchSolver()
        return [n for n, _lane in solver.candidates(base_nonce, count)]
    except Exception:
        return _linear_nonces(base_nonce, count)


_M32_SOLVER = None


def _m32_lane_order(base_nonce: int):
    """The 32-entry Turing lane permutation for this window base — the same
    order ``M32SearchSolver.candidates`` walks, cached on the solver."""
    global _M32_SOLVER
    if _M32_SOLVER is None:
        platform_py = os.path.join(_PROJECT_ROOT, "chronus/mla1517_platform", "python")
        if platform_py not in sys.path:
            sys.path.append(platform_py)
        from chronus.mla1517.mining.solver import M32SearchSolver

        _M32_SOLVER = M32SearchSolver()
    return _M32_SOLVER.turing.lane_order(base_nonce)


def device_status() -> Dict[str, object]:
    """Report which quantum-intelligent device layers are actually engaged in
    the live grind path. Fields reflect real code paths — a component listed
    in the unified-punch device but not invoked per epoch is reported false.
    """
    platform_py = os.path.join(_PROJECT_ROOT, "chronus/mla1517_platform", "python")
    status: Dict[str, object] = {
        "compass_faces": 32,  # M32 lanes = 32-face routing (12+20 dual overlay)
        "manifold_dimensions": 0,
        "intelligence_types_active": 0,
        "hash_execution_model": "physical_sha256d",
        "hash_acceptance_authority": "pool_target",
        "physical_quantum_hardware_active": False,
        "quantum_simulation_in_hash_path": False,
        "candidate_order_model": nonce_order_name(),
        "kellogg_operator_active": False,  # no operator in the mining path
        "lucas_15_attractor_active": False,  # ladder used in rate metadata, not scoring
        "lucas_15_schedule_active": nonce_order_name()
        in ("lucas15", "lucas_15", "operator"),
        "pisot_collapse_active": False,  # punch 0x03 exists, not invoked per epoch
        "cassini_invariant_active": False,  # punch 0x0E exists, not invoked per epoch
        "klein_poincare_bijection_active": False,  # not implemented in the codebase
        "m32_lane_order_active": False,
        "poincare_11d_order_active": False,
        "nonce_order": nonce_order_name(),
        "phi_filter_scoring_active": False,
        "notes": [],
    }
    try:
        if platform_py not in sys.path:
            sys.path.append(platform_py)
        from chronus.mla1517.mining.geometry import M32Topology

        topo = M32Topology()
        if topo.connected() and topo.lanes == 32:
            status["m32_lane_order_active"] = True
            status["intelligence_types_active"] += 1  # topological ordering
    except Exception as exc:
        status["notes"].append(f"m32 topology unavailable: {exc}")
    if nonce_order_name() in ("11d", "poincare11d", "poincare", "manifold"):
        try:
            from Intelligence.search_crystal import PoincareCassiniSearchEngine  # noqa: F401

            status["poincare_11d_order_active"] = True
            status["intelligence_types_active"] += 1  # 11D geodesic ordering
        except Exception as exc:
            status["notes"].append(f"poincare 11d order unavailable: {exc}")
    if status["lucas_15_schedule_active"]:
        status["intelligence_types_active"] += 1
        status["notes"].append(
            "Lucas-15 changes candidate order only; exact SHA-256d remains the "
            "acceptance authority."
        )
    status["notes"].append(
        "Quantum-algorithm simulation is evaluated separately from live mining."
    )
    return status


def mine_job(
    job: LiveJob,
    extranonce1: str,
    extranonce2_size: int,
    pipeline: Optional[HashPipeline] = None,
    nonce_window: int = 200000,
    base_nonce: int = 0,
    extranonce2_int: int = 0,
) -> dict:
    """Grind one live job: coinbase -> merkle -> header -> hash pipeline."""
    if pipeline is None:
        if HashPipeline is None:
            raise RuntimeError("HashPipeline not available")
        pipeline = HashPipeline()
    pad_len = extranonce2_size * 2
    extranonce2 = f"{extranonce2_int:0{pad_len}x}"
    if len(extranonce2) > pad_len:
        extranonce2 = extranonce2[-pad_len:]
    coinbase = build_coinbase(job.coinb1, extranonce1, extranonce2, job.coinb2)
    root = merkle_root(coinbase_hash(coinbase), job.merkle_branch)
    root_hex = root[::-1].hex()
    header = build_header80(job.version, job.prev_hash, root_hex, job.ntime, job.nbits)
    target = difficulty_to_target(job.difficulty).to_bytes(32, "big")
    if nonce_order_name() in ("m32",) and getattr(pipeline.hasher, "k_m32", None) is not None:
        try:
            res = pipeline.grind_m32(
                header, target, base_nonce, _m32_lane_order(base_nonce), nonce_window
            )
        except Exception as exc:
            # A RuntimeError is a proof-layer or binding failure — most
            # critically a device hit failing the host SHA-256d recheck.
            # That must never silently re-grind on a different arm.
            if isinstance(exc, RuntimeError):
                raise
            # Capability/shape failures only (e.g. a window that is not a
            # multiple of 32): re-walk the same m32 order through the batch
            # arm. Coverage and order are preserved; validity stays SHA256d.
            nonces = _lane_nonces(base_nonce, nonce_window, header80=header)
            res = pipeline.grind(header, target, nonces)
    else:
        nonces = _lane_nonces(base_nonce, nonce_window, header80=header)
        res = pipeline.grind(header, target, nonces)
    return {
        "job_id": job.job_id,
        "header": header.hex(),
        "target": target.hex(),
        "result": res,
        "extranonce2": extranonce2,
        "ntime": job.ntime,
        "base_nonce": base_nonce,
        "device": device_status(),
    }


_POOL_ENV = {
    "viabtc": ("VIABTC_ENDPOINT", "VIABTC_ACCOUNT", "btc.viabtc.top:3333"),
    "braiins": ("BRAIINS_ENDPOINT", "BRAIINS_ACCOUNT", "stratum.braiins.com:3333"),
}


def _env(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def _default_pool_env() -> tuple[str, str | None, str]:
    """Resolve endpoint + worker from ONE pool family.

    PYTHIA_STRATUM_* carries the canonical identity exported by the control
    API; pool-specific vars (selected by PYTHIA_POOL_PROFILE, else whichever
    pool's account is configured) supply endpoint and worker together so an
    endpoint is never paired with another pool's credentials.
    """
    profile = _env("PYTHIA_POOL_PROFILE") or ""
    endpoint_var = account_var = None
    for name in (profile, "viabtc", "braiins"):
        endpoint_var, account_var, default_endpoint = _POOL_ENV.get(
            name, (None, None, "btc.viabtc.top:3333")
        )
        if account_var and _env(account_var):
            break
    else:  # pragma: no cover - loop always exits via break or exhausts
        default_endpoint = "btc.viabtc.top:3333"
    pool = _env("PYTHIA_STRATUM_ENDPOINT", endpoint_var) or default_endpoint
    worker = _env("PYTHIA_STRATUM_WORKER", account_var)
    password = _env("STRATUM_PASSWORD", "PYTHIA_STRATUM_PASSWORD") or "x"
    return pool, worker, password


def submission_exit_code(submit_test: bool, shares_accepted: int) -> int:
    """Automation must fail when a requested live test proves no acceptance."""
    return 0 if not submit_test or shares_accepted > 0 else 2


async def _amain(argv=None) -> int:
    default_pool, default_worker, default_pass = _default_pool_env()

    parser = argparse.ArgumentParser(description="Python Stratum V1 bridge")
    parser.add_argument("--pool", default=default_pool, help="host:port or stratum+tcp://host:port")
    parser.add_argument(
        "--worker",
        default=default_worker,
        help="worker username (or PYTHIA_STRATUM_WORKER/VIABTC_ACCOUNT/BRAIINS_ACCOUNT env)",
    )
    parser.add_argument(
        "--password",
        default=default_pass,
        help="worker password (or STRATUM_PASSWORD env; default x)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="connect, get job, grind locally, do NOT submit"
    )
    parser.add_argument(
        "--submit-test",
        action="store_true",
        help="grind and submit (requires live-submit env gates)",
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="run continuous live mining loop instead of exiting after one window",
    )
    parser.add_argument("--window", type=int, default=200000, help="nonce window per batch")
    parser.add_argument(
        "--suggest-diff", type=float, default=None, help="suggest starting difficulty"
    )
    parser.add_argument(
        "--backend",
        default="auto",
        choices=["auto", "gpu", "opencl", "cpu", "cuda", "metal", "remote"],
        help="hasher backend",
    )
    parser.add_argument("--max-shares", type=int, default=None, help="halt after N accepted shares")
    parser.add_argument("--max-runtime", type=float, default=None, help="halt after N seconds")
    args = parser.parse_args(argv)
    if not args.worker:
        parser.error(
            "--worker or PYTHIA_STRATUM_WORKER/VIABTC_ACCOUNT/BRAIINS_ACCOUNT is required; "
            "no default account is assumed"
        )
    try:
        from startup_contract import validate_worker_identity

        validate_worker_identity(args.worker)
    except ImportError:
        if args.worker.strip().casefold() in {
            "account.worker",
            "your_worker",
            "your.worker",
            "worker",
            "pythia.001",
            "test.worker",
        }:
            parser.error("--worker must be a real pool identity, not a placeholder")
    except ValueError as exc:
        parser.error(str(exc))

    raw_pool = args.pool
    for prefix in ("stratum+tcp://", "tcp://", "stratum://"):
        if raw_pool.startswith(prefix):
            raw_pool = raw_pool[len(prefix) :]
    host, _, port_s = raw_pool.partition(":")
    port = int(port_s or "3333")

    max_shares = args.max_shares
    if max_shares is None and os.environ.get("HYBA_TARGET_SHARES"):
        try:
            max_shares = int(os.environ["HYBA_TARGET_SHARES"])
        except ValueError:
            pass

    max_runtime = args.max_runtime
    if max_runtime is None and os.environ.get("HYBA_MAX_RUNTIME_SECONDS"):
        try:
            max_runtime = float(os.environ["HYBA_MAX_RUNTIME_SECONDS"])
        except ValueError:
            pass

    bridge = StratumBridge(host, port, args.worker, args.password)
    print(f"Connecting to Stratum pool {host}:{port} as {args.worker} ...")
    await bridge.connect()
    await bridge.handshake(suggest_diff=args.suggest_diff)
    print(
        f"Authorized successfully. extranonce1={bridge.extranonce1} "
        f"extranonce2_size={bridge.extranonce2_size}"
    )

    listener = asyncio.create_task(bridge.listen_forever())

    print(f"Initializing hash pipeline (backend={args.backend}) ...")
    pipeline = HashPipeline(hasher_backend=args.backend)
    print(f"Pipeline active: backend={pipeline.hasher.backend} device={pipeline.hasher.device}")

    t_start = time.perf_counter()
    extranonce2_counter = 0
    base_nonce = 0
    current_job_marker = None
    total_hashes = 0
    total_batches = 0

    emitter = None
    if args.continuous:
        try:
            from worker_lifecycle import HeartbeatEmitter

            emitter = HeartbeatEmitter(os.getenv("PYTHIA_WORKER_NAME", "stratum-bridge"))
            emitter.__enter__()
        except Exception:
            if os.getenv("PYTHIA_WORKER_NAME"):
                # Supervised workers are under the heartbeat contract —
                # failing to establish the channel must fail the worker.
                raise
            print("[heartbeat] emitter unavailable; running unsupervised")

    try:
        while True:
            elapsed = time.perf_counter() - t_start
            if max_runtime and elapsed >= max_runtime:
                print(f"\n[HALT] Reached max runtime limit ({max_runtime}s).")
                break
            if max_shares and bridge.shares_accepted >= max_shares:
                print(
                    f"\n[HALT] Reached target accepted shares ({bridge.shares_accepted}/{max_shares})."
                )
                break

            job = bridge.last_job
            if job is None or not job.job_id:
                try:
                    job = await bridge.wait_for_job(timeout=10.0)
                except TimeoutError:
                    print("Waiting for initial mining.notify job from pool...")
                    await asyncio.sleep(0.5)
                    continue

            # Restart detection keyed on the wire facts — job_id plus the
            # clean-job generation — never by mutating the cached LiveJob.
            job_marker = (job.job_id, bridge.clean_job_generation)
            if job_marker != current_job_marker:
                current_job_marker = job_marker
                base_nonce = 0
                print(
                    f"\n[NEW JOB] ID={job.job_id} difficulty={job.difficulty} "
                    f"nbits={job.nbits} prev={job.prev_hash[:16]}..."
                )

            clean_job_generation = bridge.clean_job_generation
            out = await asyncio.to_thread(
                mine_job,
                job,
                bridge.extranonce1,
                bridge.extranonce2_size,
                pipeline=pipeline,
                nonce_window=args.window,
                base_nonce=base_nonce,
                extranonce2_int=extranonce2_counter,
            )
            if not bridge.is_job_valid(clean_job_generation):
                print(f"[STALE JOB] Discarded completed work for {job.job_id}")
                continue
            res = out["result"]
            total_hashes += res.hashes_computed
            total_batches += 1
            now_elapsed = time.perf_counter() - t_start
            avg_hps = total_hashes / now_elapsed if now_elapsed > 0 else 0.0
            order = nonce_order_name()
            # The M32 order walks one lane per step — every arm's window
            # partitions across 32 disjoint lanes; other orders are single
            # traversal classes over the same space.
            lanes = 32 if order == "m32" else 1
            # Deterministic hashrate: the configured target is the driver —
            # the loop is throttled so measured rate converges to
            # min(target, physical). 0 = unthrottled (physical rate).
            target_hs = _configured_target_hs()
            if target_hs > 0:
                expected_elapsed = total_hashes / target_hs
                pacing_delay = expected_elapsed - (time.perf_counter() - t_start)
                if pacing_delay > 0:
                    await asyncio.sleep(min(pacing_delay, 30.0))
                now_elapsed = time.perf_counter() - t_start
                avg_hps = total_hashes / now_elapsed if now_elapsed > 0 else 0.0
            if emitter is not None:
                emitter.report(
                    hashrate_hs=res.measured_hps,
                    hashrate_avg_hs=avg_hps,
                    target_hashrate_hs=target_hs,
                    total_hashes=total_hashes,
                    batches=total_batches,
                    shares_accepted=bridge.shares_accepted,
                    shares_rejected=bridge.shares_rejected,
                    job_id=job.job_id,
                    backend=pipeline.hasher.backend,
                    device=pipeline.hasher.device,
                    solver_lanes=lanes,
                    nonce_window=args.window,
                    nonce_order=order,
                    extranonce2=extranonce2_counter,
                    coverage_nonces=(base_nonce + args.window) & 0xFFFFFFFF,
                )

            preview = _lane_nonces(base_nonce, 8)
            print(
                f"[{time.strftime('%H:%M:%S')}] Job {job.job_id} | "
                f"nonce [0x{base_nonce:08x}..0x{(base_nonce + args.window - 1) & 0xFFFFFFFF:08x}] | "
                f"order={'linear' if preview == list(range(base_nonce, base_nonce + 8)) else 'm32'} "
                f"head={[hex(n) for n in preview]} | "
                f"batch: {res.measured_hps/1e6:.2f} MH/s | "
                f"avg: {avg_hps/1e6:.2f} MH/s | "
                f"total: {total_hashes:,} | "
                f"shares: {bridge.shares_accepted} acc / {bridge.shares_rejected} rej"
            )

            if res.mining_success:
                nonce_hex = f"{res.winning_nonce:08x}"
                win_hash_hex = res.winning_hash[::-1].hex()
                winning_lane = (res.winning_nonce - base_nonce) % 32 if order == "m32" else 0
                print("\n========================================================")
                print(f"  WINNING NONCE FOUND: 0x{nonce_hex}  (lane {winning_lane})")
                print(f"  Digest: {win_hash_hex}")
                print(f"  Target: {out['target']}")
                print("========================================================")
                if emitter is not None:
                    emitter.report(winning_nonce=res.winning_nonce, winning_lane=winning_lane)

                if args.dry_run or not args.submit_test:
                    print(
                        "dry-run: NOT submitting share to pool (use --submit-test with live gates)"
                    )
                    if not args.continuous:
                        return 0
                else:
                    if not bridge.is_job_valid(clean_job_generation):
                        print(f"[STALE JOB] Refusing submission for {job.job_id}")
                        continue
                    submission = bridge.submit_share(
                        job.job_id, out["extranonce2"], out["ntime"], nonce_hex
                    )
                    if submission is None:
                        print(
                            "submit GATED: live-submit env not approved (check HYBA_ENABLE_LIVE_SHARE_SUBMIT)"
                        )
                    else:
                        verdict = await submission
                        print(
                            f"Pool submission verdict: {'*** ACCEPTED ***' if verdict else 'REJECTED'}"
                        )
                        if verdict and not args.continuous:
                            return 0

            base_nonce = (base_nonce + args.window) & 0xFFFFFFFF
            if base_nonce < args.window:
                extranonce2_counter += 1
                base_nonce = 0
                print(f"[EXTRANONCE2] Incremented to {extranonce2_counter:08x}")

            if not args.continuous:
                if res.mining_success:
                    return 0
                print("Single window complete. (Run with --continuous for live mining loop)")
                return 0

            await asyncio.sleep(0.001)

        return submission_exit_code(args.submit_test, bridge.shares_accepted)

    except KeyboardInterrupt:
        print("\nMining stopped by operator (Ctrl+C).")
        return 0
    finally:
        if emitter is not None:
            emitter.__exit__(None, None, None)
        listener.cancel()
        await bridge.disconnect()
        session_el = time.perf_counter() - t_start
        session_hps = total_hashes / session_el if session_el > 0 else 0.0
        print(
            f"Disconnected. Session summary: {total_hashes:,} hashes computed in "
            f"{session_el:.1f}s (measured live rate {session_hps/1e6:.2f} MH/s), "
            f"{bridge.shares_accepted} shares accepted, {bridge.shares_rejected} shares rejected."
        )


def main(argv=None) -> int:
    load_env_file()
    return asyncio.run(_amain(argv))


if __name__ == "__main__":
    sys.exit(main())

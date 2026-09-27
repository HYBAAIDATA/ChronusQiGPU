"""
HYBA Stratum Client (V1/V2 Protocol Engine)
============================================
Features:
- Live-submit firewall gate (HYBA_ENABLE_LIVE_SHARE_SUBMIT / HYBA_LIVE_SHARE_APPROVAL_ID)
- Real Merkle root computation (coinbase + extranonces + merkle branch)
- Real 80-byte block header construction & double-SHA256 validation
- Per-request monotonic ID mapping with asyncio Futures
- Zero metric inflation: pool-confirmed only recorded upon actual pool ACK
- Zero double-counting of accepted/rejected shares
- No simulation mode: connection failure is surfaced honestly (never a fake
  pool session) so the Salamander supervisor owns recovery
- Graceful shutdown: close()/disconnect() cancels the background listener
  task instead of abandoning it (no more "Task was destroyed but it is
  pending!" at process exit)
- Bounded exponential backoff reconnect on unexpected disconnect (dropped
  TCP, remote EOF) so a single lost connection cannot silently stop the
  miner from ever receiving another job
- Session/job epochs: reconnects and clean_jobs notifies invalidate prior
  job context before it can be submitted; pending submissions are failed
  honestly and late pool verdicts reconcile through a bounded late-ACK
  window instead of being dropped
- Split share verdict counters (pool_accepted/pool_rejected vs
  firewall_accepted/firewall_rejected vs timed-out/transport-failed) so a
  local validation verdict can never masquerade as pool confirmation
- Byte-order rules for header fields and mining.submit's nonce parameter are
  ported from pooler/cpuminer's proven reference implementation
  (https://github.com/pooler/cpuminer): version/prevhash/ntime/nbits are
  inserted RAW/verbatim, merkle_root gets a per-4-byte-word reversal, and the
  wire-format nonce sent to the pool is little-endian encoded (see
  nonce_to_wire_hex()) -- distinct from the natural/display hex form used in
  logs and local header assembly. connect() also blocks for and checks the
  mining.authorize response instead of assuming success.
"""

from __future__ import annotations
import os
import json
import time
import math
import struct
import asyncio
import hashlib
import logging
from typing import Optional, Dict, Any, Tuple, List, Callable, Deque
from collections import deque
from dataclasses import dataclass

try:
    from mining.evidence import record_mining_event, MiningTruthClass
except ImportError:
    try:
        from python_backend.mining.evidence import record_mining_event, MiningTruthClass
    except ImportError:
        record_mining_event = None  # type: ignore
        MiningTruthClass = None  # type: ignore

try:
    from .viabtc_worker import resolve_viabtc_worker

    _VIABTC_WORKER_SOURCE = "upstream"
except ImportError:  # pragma: no cover - invoked with unusual root paths
    try:
        from python_backend.pythia_mining.viabtc_worker import resolve_viabtc_worker

        _VIABTC_WORKER_SOURCE = "python_backend"
    except ImportError:  # pragma: no cover - resolver module absent from this tree

        _VIABTC_WORKER_SOURCE = "fallback"

        def resolve_viabtc_worker(explicit=None):
            """Minimal fallback worker resolver used when viabtc_worker.py
            is absent from the deployment tree (e.g. standalone checkout)."""
            candidate = (
                explicit or os.getenv("HYBA_POOL_WORKER") or os.getenv("HYBA_POOL_VIABTC_USERNAME")
            )
            return str(candidate).strip() if candidate else None


if _VIABTC_WORKER_SOURCE == "fallback":
    # Loud by design: a silent shim is how "works in dev, breaks in prod"
    # happens. The fallback exists for standalone/testability only -- every
    # import and every get_stats() snapshot records which resolver is live.
    import warnings

    warnings.warn(
        "stratum_client: viabtc_worker.py absent; using env-based fallback "
        "worker resolver. This is a testing shim, not a production "
        "substitute -- verify against the upstream module before deploying.",
        RuntimeWarning,
        stacklevel=2,
    )
    logging.warning(
        "[STRATUM] viabtc_worker.py absent -- fallback worker resolver active "
        "(viabtc_source=fallback)."
    )


# Request id returned by submit_share() for shares that never reached the
# wire (stale job, dead session, firewall path). Named so call sites can
# distinguish "no request was made" from a real pool correlation id.
UNSUBMITTED_REQUEST_ID = 0

# Stratum V1 handshake request ids. mining.submit ids are seeded ABOVE this
# range and must never reuse it: a submit id colliding with 1 or 2 would be
# consumed by the authorize branch of _listen_loop and the share's verdict
# would be lost. Pending futures are checked before the handshake shortcut
# and submit_share() hard-refuses ids in this range.
_HANDSHAKE_REQUEST_IDS = frozenset({1, 2})
_SUBMIT_ID_FLOOR = 3

# Bound on the late-ACK reconciliation map: verdicts arriving after the
# submit timeout stay attributable for this long (or until this many
# entries accumulate, whichever expires first).
_LATE_ACK_MAX_ENTRIES = 128


def double_sha256(data: bytes) -> bytes:
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def compute_stratum_merkle_root(
    coinb1_hex: str,
    extranonce1_hex: str,
    extranonce2_hex: str,
    coinb2_hex: str,
    merkle_branch: List[str],
) -> str:
    coinbase_hex = (
        (coinb1_hex or "") + (extranonce1_hex or "") + (extranonce2_hex or "") + (coinb2_hex or "")
    )
    if not coinbase_hex:
        return "0" * 64

    coinbase_bytes = bytes.fromhex(coinbase_hex)
    coinbase_hash = double_sha256(coinbase_bytes)

    merkle_root_bytes = coinbase_hash
    for branch_hex in merkle_branch:
        if not branch_hex:
            continue
        branch_bytes = bytes.fromhex(branch_hex)
        combined = merkle_root_bytes + branch_bytes
        merkle_root_bytes = double_sha256(combined)

    return merkle_root_bytes.hex()


def _raw_field_bytes(hex_str: Optional[str], nbytes: int, default_hex: str) -> bytes:
    """
    Decode a Stratum field to exactly `nbytes` RAW bytes, verbatim, with no
    endian reinterpretation.

    This is the byte-order rule verified against pooler/cpuminer's
    stratum_notify()/stratum_gen_work() (cpu-miner.c + util.c on GitHub,
    https://github.com/pooler/cpuminer) -- the canonical, still-functional
    reference Stratum V1 client: version, prevhash, ntime and nbits are
    hex2bin()'d directly into the job struct with NO byte reordering, and
    copied 1:1 into the 80-byte header (its le32dec()-then-native-uint32-store
    is a byte-identity round trip on a little-endian host). Pools format
    these fields ready for direct header insertion -- re-encoding them as a
    Python int and struct.pack("<I", ...)'ing them back out silently reverses
    the bytes and produces a header that will never validate.
    """
    if isinstance(hex_str, (tuple, list)):
        hex_str = hex_str[0] if hex_str else ""
    if not isinstance(hex_str, str):
        hex_str = str(hex_str) if hex_str is not None else ""
    h = hex_str.strip() or default_hex
    h = h.zfill(nbytes * 2)
    try:
        b = bytes.fromhex(h)
    except ValueError:
        b = bytes.fromhex(default_hex.zfill(nbytes * 2))
    return b[-nbytes:].rjust(nbytes, b"\x00")


def build_stratum_block_header(
    version_hex: str,
    prevhash_hex: str,
    merkle_root_hex: str,
    ntime_hex: str,
    nbits_hex: str,
    nonce_hex: str,
) -> bytes:
    """
    Construct the exact 80-byte Bitcoin block header from Stratum job
    parameters, using the byte-order rules verified against pooler/cpuminer's
    proven stratum_gen_work() (cpu-miner.c):

      - version, prevhash, ntime, nbits: RAW bytes, exactly as sent by the
        pool -- no reordering (see _raw_field_bytes docstring).
      - merkle_root: computed locally via double-SHA256, then each 4-byte
        WORD is individually byte-reversed (cpuminer's be32dec() insertion),
        with word order left unchanged. This is NOT the same as reversing
        the full 32 bytes.
      - nonce: little-endian encoding of the nonce integer
        (cpuminer's le32enc(work->data[19]) round trip == struct.pack("<I", n)).
    """
    v_bytes = _raw_field_bytes(version_hex, 4, "00000001")
    p_bytes = _raw_field_bytes(prevhash_hex, 32, "00" * 32)

    m_raw = _raw_field_bytes(merkle_root_hex, 32, "00" * 32)
    m_bytes = b"".join(m_raw[i : i + 4][::-1] for i in range(0, 32, 4))

    t_bytes = _raw_field_bytes(ntime_hex, 4, hex(int(time.time()))[2:].zfill(8))
    b_bytes = _raw_field_bytes(nbits_hex, 4, "1d00ffff")

    # Nonce: this field WAS already correct -- little-endian packing of the
    # raw nonce integer, not a verbatim/raw copy like the fields above.
    n_int = int(nonce_hex, 16) if nonce_hex else 0
    n_bytes = struct.pack("<I", n_int & 0xFFFFFFFF)

    header = v_bytes + p_bytes + m_bytes + t_bytes + b_bytes + n_bytes
    return header


def nonce_to_wire_hex(nonce) -> str:
    """
    Convert a nonce (Python int, or the natural/display hex string produced
    by e.g. hex(n)[2:].zfill(8)) into the little-endian wire-format hex
    string required by the `mining.submit` JSON-RPC call.

    Reference: pooler/cpuminer's submit_upstream_work() does
    `le32enc(&nonce, work->data[19]); bin2hex(noncestr, &nonce, 4);` --
    i.e. struct.pack("<I", n).hex() -- NOT a straight hex passthrough of the
    nonce's natural/display representation. Submitting the natural-order hex
    string directly is a classic Stratum bug: the pool will reconstruct a
    different header than the one that was actually validated locally, so
    real shares get silently rejected.
    """
    if isinstance(nonce, int):
        n_int = nonce
    else:
        s = str(nonce).strip()
        n_int = int(s, 16) if s else 0
    return struct.pack("<I", n_int & 0xFFFFFFFF).hex()


# ============================================================================
# STRATUM CLIENT CLASS
# ============================================================================


@dataclass
class StratumJob:
    job_id: str
    prevhash: str
    coinb1: str
    coinb2: str
    merkle_branch: List[str]
    version: str
    nbits: str
    ntime: str
    clean_jobs: bool = False


class StratumClient:
    """HYBA Stratum Client. Operator-provided ViaBTC details: Pool1 3333, Pool2 443, PYTHIA.001 / 123."""

    # btc.viabtc.io is the correct, confirmed-live ViaBTC hostname (verified
    # by a real TCP handshake + mining.subscribe/authorize/notify cycle --
    # see stratum_client live-connection test). Primary 3333 is plain TCP;
    # 443 is ViaBTC's documented SSL/failover port (auto-TLS'd by connect()).
    DEFAULT_POOLS = [
        "127.0.0.1:3333",
        "btc.viabtc.io:3333",
        "btc.viabtc.io:443",
        "btc.viabtc.top:3333",
        "btc.viabtc.io:25",
        "btc.viabtc.top:25",
        "bitcoin.viabtc.io:3333",
        "bitcoin.viabtc.io:443",
    ]

    def __init__(self, pool_url: str = None, worker_name: str = None, password: str = None):
        # DEFAULT POOL: Braiins. Reads the generic HYBA_POOL_* overrides first
        # (set from the frontend via /api/mining/pools and persisted to .env),
        # then falls back to the ViaBTC-specific legacy vars, then the Braiins
        # default. This is what makes `npm start` connect to Braiins by default.
        raw_url = (
            pool_url
            or os.getenv("HYBA_POOL_URL")
            or os.getenv("HYBA_POOL_VIABTC_URL", "stratum+tcp://stratum.braiins.com:3333")
        )
        self.pool_url = self._clean_url(raw_url)
        failover = os.getenv("HYBA_POOL_URL_FAILOVER") or os.getenv(
            "HYBA_POOL_VIABTC_URL_FAILOVER", "stratum+tcp://btc.viabtc.io:3333"
        )
        self.failover_url = self._clean_url(failover)
        resolved = resolve_viabtc_worker(explicit=worker_name)
        # No hardcoded credential fallback. Shipping "PYTHIA.001"/"123" as a
        # default meant an unconfigured process authenticated as a real worker
        # against a real pool. Absent credentials now yield empty strings, and
        # connect() refuses to dial rather than authorising as someone else.
        self.worker_name = (
            resolved
            or worker_name
            or os.getenv("HYBA_POOL_WORKER")
            or os.getenv("HYBA_POOL_VIABTC_USERNAME", "").strip()
        )
        if password is not None:
            self.password = password
        else:
            self.password = (
                os.getenv("HYBA_POOL_PASSWORD")
                or os.getenv("HYBA_POOL_VIABTC_PASSWORD", "").strip()
            )
        self.status = "DISCONNECTED"
        self.connected_at: Optional[float] = None
        # Share verdict counters split by authority: a locally-validated
        # share is NOT pool-confirmed truth, so the firewall path and the
        # pool ACK path advance separate counters. shares_accepted /
        # shares_rejected remain available below as backward-compatible
        # aggregate properties.
        self.pool_accepted = 0
        self.pool_rejected = 0
        self.firewall_accepted = 0
        self.firewall_rejected = 0
        self.shares_timed_out = 0
        self.shares_transport_failed = 0
        self.shares_failed = 0
        self.client_reconnects = 0
        self.latency_ms = 0.0
        # GAP-CLOSURE-001: share-submission path timing (notify -> submit ->
        # ACK). Measured on the REAL submission lane with nothing mocked: the
        # wait component timestamps the newest template arrival, the RTT
        # component spans wire write through pool ACK verdict (accepted,
        # rejected-by-result, 5s timeout, or transport failure -- every path
        # closes the interval honestly). Rolling window keeps memory bounded.
        self.current_job_received_at: Optional[float] = None
        self.last_submit_rtt_ms: Optional[float] = None
        self.last_submit_wait_ms: Optional[float] = None
        self.submit_rtt_samples_ms: Deque[float] = deque(maxlen=64)
        # SOLVE-10MIN lever telemetry: outbound difficulty suggestion facts.
        self.suggest_difficulty_sent: Optional[int] = None
        self.last_suggest_rtt_ms: Optional[float] = None
        self.last_heartbeat = time.time()
        self.current_job: Optional[Dict[str, Any]] = None
        self.job_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        self.clean_job_event: asyncio.Event = asyncio.Event()
        self._job_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self.difficulty = 1.0
        self.target = "00000000ffff0000000000000000000000000000000000000000000000000000"
        self.extranonce1: Optional[str] = "00000000"
        self.extranonce2_size: int = 4
        self._extranonce2_counter: int = 0
        # Submit request ids are seeded ABOVE the reserved handshake range
        # and are NEVER reset in connect(): a reconnect must not re-issue a
        # request id the pool already answered, and a submit id landing on
        # 1 or 2 would be swallowed by the authorize shortcut in
        # _listen_loop instead of resolving the share.
        self._submit_counter: int = 10
        # Pending submissions carry the full submission context (future +
        # job_id + extranonce1 + epochs at submit time) so a pool verdict is
        # attributed to the job the share was built against, not whichever
        # job happens to be current when the ACK arrives.
        self._pending_futures: Dict[int, Dict[str, Any]] = {}
        # Timed-out submissions are retained for a bounded grace period so a
        # late pool verdict is reconciled into the counters instead of being
        # silently dropped. Entries hold (job_id, epochs, expiry).
        self._late_acks: Dict[int, Dict[str, Any]] = {}
        self._late_ack_grace_seconds: float = float(
            os.getenv("HYBA_LATE_ACK_GRACE_SECONDS", "60") or 60
        )
        self.late_acks_reconciled: int = 0
        # session_epoch bumps on every new pool session and on unexpected
        # disconnect; job_epoch bumps on every clean_jobs notify. Both are
        # recorded on each submission so stale-context shares and
        # stale-session ACKs are refused rather than misattributed.
        self.session_epoch: int = 0
        self.job_epoch: int = 0
        self.submit_timeout_seconds: float = float(
            os.getenv("HYBA_SUBMIT_TIMEOUT_SECONDS", "5.0") or 5.0
        )
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._running: bool = False
        # Lifecycle handles for a graceful shutdown path: the background
        # listener task must be cancelled and awaited on close(), never
        # just abandoned (that produced "Task was destroyed but it is
        # pending!" at process exit prior to this fix).
        self._listen_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._reconnecting: bool = False
        self._closing: bool = False
        # Set for the whole duration of close(): a lazy connect() (e.g. from
        # submit_share) racing an in-flight shutdown must not re-arm the
        # client.
        self._close_in_progress: bool = False
        # Bounded exponential backoff for unexpected disconnects (dropped
        # TCP, remote EOF, socket error). Without this, one dropped
        # connection silently stopped the miner from ever receiving a
        # new job again.
        self._reconnect_base_delay: float = 1.0
        self._reconnect_max_delay: float = 60.0
        self.connection_attempts: int = 0
        self.reconnect_attempts: int = 0
        self.disconnect_events: int = 0
        self.jobs_received: int = 0
        self.stale_submissions_rejected: int = 0

    @property
    def shares_accepted(self) -> int:
        """Aggregate accepted count: pool-confirmed + firewall-validated.

        Backward-compatibility shim -- use pool_accepted /
        firewall_accepted in telemetry that must not conflate a local
        validation verdict with the pool's own accounting.
        """
        return self.pool_accepted + self.firewall_accepted

    @property
    def shares_rejected(self) -> int:
        """Aggregate non-accepted count: pool rejects, firewall rejects,
        ACK timeouts and transport failures."""
        return (
            self.pool_rejected
            + self.firewall_rejected
            + self.shares_timed_out
            + self.shares_transport_failed
        )

    def _invalidate_session(self, reason: str) -> None:
        """Retire all context belonging to the previous pool session.

        Called on unexpected disconnect (remote EOF / socket error detected
        by the listener) and whenever a new session socket is opened.
        Pending submissions are failed honestly with ConnectionError rather
        than left to hang to timeout, the job context is dropped (its
        extranonce1 is dead), the late-ACK window closes, and both epochs
        bump so a stale-session verdict can never be reconciled into the
        new session's counters.
        """
        self.session_epoch += 1
        self.job_epoch += 1
        self.current_job = None
        self.current_job_received_at = None
        self.clean_job_event.set()
        self.drain_jobs()
        self._late_acks.clear()
        for req_id, rec in list(self._pending_futures.items()):
            fut = rec["future"]
            if not fut.done():
                fut.set_exception(
                    ConnectionError(
                        f"Stratum session invalidated ({reason}) while awaiting pool response"
                    )
                )
        self._pending_futures.clear()

    def _prune_late_acks(self) -> None:
        """Drop expired late-ACK entries and keep the map bounded."""
        now = time.monotonic()
        for req_id in [k for k, rec in self._late_acks.items() if rec.get("expires_at", 0.0) < now]:
            self._late_acks.pop(req_id, None)
        while len(self._late_acks) > _LATE_ACK_MAX_ENTRIES:
            oldest = min(self._late_acks, key=lambda k: self._late_acks[k].get("expires_at", 0.0))
            self._late_acks.pop(oldest, None)

    @staticmethod
    def _clean_url(url: str) -> str:
        if not url:
            return "btc.viabtc.io:3333"
        cleaned = url.strip()
        for prefix in ("stratum+ssl://", "stratum+tcp://", "stratum://", "ssl://", "tcp://"):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix) :]
                break
        return cleaned.strip()

    def _pool_priority(self, primary: str) -> List[str]:
        ordered = [primary, self.failover_url] + self.DEFAULT_POOLS
        seen = set()
        out = []
        for pool in ordered:
            if pool and pool not in seen:
                seen.add(pool)
                out.append(pool)
        return out

    @staticmethod
    def _flag(key: str) -> bool:
        return os.getenv(key, "").strip().lower() in ("1", "true", "yes", "on")

    def _egress_permitted(self) -> bool:
        """Whether this client may open a socket to a third-party pool.

        Requires BOTH an explicit arming flag and real credentials. A miner
        with no credentials that dials anyway would authenticate as whatever
        default was compiled in -- which is exactly the defect this closes.
        """
        armed = self._flag("HYBA_ENABLE_LIVE_STRATUM") or self._flag(
            "HYBA_ENABLE_MINING_AUTOCONNECT"
        )
        if not armed:
            logging.warning(
                "[STRATUM] connect() refused: pool egress is not armed. "
                "Set HYBA_ENABLE_LIVE_STRATUM=true to permit it."
            )
            return False
        if not self.worker_name or not self.password:
            logging.error(
                "[STRATUM] connect() refused: pool egress is armed but credentials are "
                "missing (HYBA_POOL_VIABTC_USERNAME / HYBA_POOL_VIABTC_PASSWORD). "
                "Refusing to authenticate with a placeholder identity."
            )
            return False
        return True

    @staticmethod
    def is_live_submit_approved() -> bool:
        enable = os.getenv("HYBA_ENABLE_LIVE_SHARE_SUBMIT", "false").lower() == "true"
        approval_id = os.getenv("HYBA_LIVE_SHARE_APPROVAL_ID", "")
        autonomous = os.getenv("HYBA_AUTONOMOUS_EXTERNAL_ACTIONS", "false").lower() == "true"
        return enable and (len(approval_id) > 0 or autonomous)

    async def suggest_difficulty(self, difficulty: int) -> bool:
        """Ask the pool to move THIS worker's var-diff target to `difficulty`.

        SOLVE-10MIN lever (live-run directive 2026-08-27): var-diff normally
        converges toward a small-hasrate worker's sustainable difficulty only
        AFTER shares start flowing -- a chicken-and-egg that dominates
        time-to-first-share for CPU/iGPU miners. Stratum's
        mining.suggest_difficulty states the difficulty the arithmetic
        supports BEFORE the first hash lands, collapsing that convergence.

        Fail-open and best-effort BY DESIGN:
          - Firewalled behind the SAME gate as share submission (an outbound
            protocol write is an external action).
          - Pools honor suggestions silently through var-diff adjustments;
            they never acknowledge them. We record sent-not-acknowledged and
            NEVER claim acceptance (truth doctrine: no invented counters).
        """
        try:
            d_int = int(difficulty)
        except (TypeError, ValueError):
            logging.warning("[STRATUM] suggest_difficulty ignored: non-integer %r", difficulty)
            return False
        if d_int <= 0:
            return False
        if not self.is_live_submit_approved():
            logging.info(
                "[STRATUM] suggest_difficulty(%s) skipped: live external actions not approved",
                d_int,
            )
            return False
        if self.status != "CONNECTED" or self._writer is None:
            logging.info("[STRATUM] suggest_difficulty(%s) skipped: not connected", d_int)
            return False

        # Request-id namespace far above submit counter start (10+); the
        # listener resolves futures only for ids it registered, so an unused
        # id here is a tolerated orphan response, not an error condition.
        self._suggest_counter = getattr(self, "_suggest_counter", 0) + 1
        req_id = 500 + (self._suggest_counter % 400)
        wire_msg = (
            json.dumps(
                {
                    "id": req_id,
                    "method": "mining.suggest_difficulty",
                    "params": [d_int],
                }
            )
            + "\n"
        )
        try:
            t0 = time.perf_counter()
            self._writer.write(wire_msg.encode())
            await self._writer.drain()
            self.last_suggest_rtt_ms = round((time.perf_counter() - t0) * 1000.0, 3)
            self.suggest_difficulty_sent = d_int
            logging.info(
                "[STRATUM] suggested difficulty=%s [ReqID=%s] in %.3fms "
                "(honored silently via var-diff; not ACKed by design)",
                d_int,
                req_id,
                self.last_suggest_rtt_ms,
            )
            return True
        except Exception as exc:  # a failed suggestion must never kill the connection
            logging.warning("[STRATUM] suggest_difficulty write failed (non-fatal): %s", exc)
            return False

    def register_job_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self._job_callbacks.append(callback)

    async def next_job(self) -> Dict[str, Any]:
        return await self.job_queue.get()

    def drain_jobs(self) -> int:
        drained = 0
        while True:
            try:
                self.job_queue.get_nowait()
                drained += 1
            except asyncio.QueueEmpty:
                return drained

    def _get_next_extranonce2(self) -> str:
        self._extranonce2_counter += 1
        self._extranonce2_counter %= 1 << (self.extranonce2_size * 8)
        return f"{self._extranonce2_counter:0{self.extranonce2_size * 2}x}"

    def _difficulty_to_target(self, difficulty: float) -> str:
        if math.isnan(difficulty) or math.isinf(difficulty) or difficulty <= 0:
            difficulty = 1.0
        max_target = 0x00000000FFFF0000000000000000000000000000000000000000000000000000
        target_val = int(max_target / difficulty)
        max_256 = (1 << 256) - 1
        target_val = min(max(1, target_val), max_256)
        return f"{target_val:064x}"

    def set_difficulty(self, difficulty: float) -> None:
        if math.isnan(difficulty) or math.isinf(difficulty) or difficulty <= 0:
            difficulty = 1.0
        self.difficulty = difficulty
        self.target = self._difficulty_to_target(difficulty)

    def parse_stratum_message(self, message: dict) -> Optional[Dict[str, Any]]:
        try:
            if not isinstance(message, dict):
                return None
            method = message.get("method")
            params = message.get("params", [])

            if method == "mining.notify":
                if not isinstance(params, list) or len(params) == 0:
                    return None

                version_raw = params[5] if len(params) > 5 else "00000000"
                if isinstance(version_raw, list):
                    version = version_raw[0] if len(version_raw) > 0 else "00000000"
                else:
                    version = str(version_raw) if version_raw else "00000000"

                if len(params) == 0 or params[0] is None or not str(params[0]).strip():
                    logging.warning(
                        "Ignoring malformed Stratum notify without a non-empty job id: %s", message
                    )
                    return None
                job_id = str(params[0]).strip()
                job = {
                    "job_id": job_id,
                    "prevhash": (
                        str(params[1]) if len(params) > 1 and params[1] is not None else "0" * 64
                    ),
                    "coinb1": str(params[2]) if len(params) > 2 and params[2] is not None else "",
                    "coinb2": str(params[3]) if len(params) > 3 and params[3] is not None else "",
                    "merkle_branch": (
                        params[4] if len(params) > 4 and isinstance(params[4], list) else []
                    ),
                    "version": version,
                    "nbits": (
                        str(params[6]) if len(params) > 6 and params[6] is not None else "1d00ffff"
                    ),
                    "ntime": (
                        str(params[7])
                        if len(params) > 7 and params[7] is not None
                        else hex(int(time.time()))[2:].zfill(8)
                    ),
                    "clean_jobs": bool(params[8]) if len(params) > 8 else False,
                }
                if job["clean_jobs"]:
                    # clean_jobs=true retires every previously issued job:
                    # bump the job epoch so in-flight work and submissions
                    # computed against retired templates are refused before
                    # they reach the wire.
                    self.job_epoch += 1
                    self.clean_job_event.set()
                    self.drain_jobs()
                # Tag the job with the epochs it was issued under so
                # submit_share() and the mining loop can refuse work that
                # survived a clean_jobs notify or a reconnect.
                job["job_epoch"] = self.job_epoch
                job["session_epoch"] = self.session_epoch
                self.current_job_received_at = time.monotonic()  # GAP-CLOSURE-001 anchor
                self.current_job = job
                self.jobs_received += 1
                self.job_queue.put_nowait(job)
                for callback in list(self._job_callbacks):
                    try:
                        callback(job)
                    except Exception as callback_exc:
                        logging.error(
                            f"Stratum job callback failed for job {job_id}: {callback_exc}"
                        )
                logging.info(
                    f"Stratum job received from ViaBTC: ID={job_id}, Version={version}, clean_jobs={job['clean_jobs']}"
                )
                return job

            elif method == "mining.set_difficulty":
                if not isinstance(params, list) or len(params) == 0:
                    diff = 1.0
                else:
                    try:
                        diff = float(params[0]) if params[0] is not None else 1.0
                    except (ValueError, TypeError):
                        diff = 1.0

                if math.isnan(diff) or math.isinf(diff) or diff <= 0:
                    diff = 1.0

                self.difficulty = diff
                self.target = self._difficulty_to_target(diff)
                logging.info(f"ViaBTC difficulty set to: {diff} | Target: {self.target[:16]}...")
                return {"difficulty": diff}

            elif method == "client.reconnect":
                # Soft reconnect: the pool asks us to move host/port WITHOUT
                # closing this socket (Stratum v1.0.0 / ViaBTC behavior).
                # In-flight shares stay valid -- the pool will still ACK
                # them -- so we must NOT bump session_epoch or fail pending
                # futures here. Record and log only; the subsequent
                # connect() (if we act on it) performs the invalidation.
                url = str(params[0]) if len(params) > 0 else ""
                port = str(params[1]) if len(params) > 1 else ""
                self.client_reconnects = getattr(self, "client_reconnects", 0) + 1
                logging.warning(
                    "[STRATUM] client.reconnect received (url=%s port=%s, #%d); "
                    "pending submissions remain valid on this session",
                    url,
                    port,
                    self.client_reconnects,
                )
                return {"client_reconnect": {"url": url, "port": port}}

            return message
        except Exception as e:
            logging.error(f"Error parsing stratum message safely: {e}")
            return None

    def validate_sha256d(self, header_hex: str, target_hex: str = None) -> bool:
        try:
            target = target_hex or self.target
            header_bytes = bytes.fromhex(header_hex)
            first_pass = hashlib.sha256(header_bytes).digest()
            second_pass = hashlib.sha256(first_pass).digest()
            hash_hex = second_pass[::-1].hex()
            return int(hash_hex, 16) <= int(target, 16)
        except Exception as e:
            logging.error(f"SHA256d validation error: {e}")
            return False

    async def _listen_loop(self) -> None:
        """Continuous background listener for incoming Stratum notifications & submission responses.

        Exits in one of three honest ways:
        1. Cancelled via close()/disconnect() — deliberate shutdown, no reconnect scheduled.
        2. Remote EOF or socket error — unexpected disconnect, schedules a
           bounded-backoff reconnect (see _reconnect_with_backoff) instead of
           silently going quiet.
        3. status changed away from CONNECTED/CONNECTING by other code — loop
           condition ends the function normally.
        """
        try:
            while self.status in ["CONNECTED", "CONNECTING"] and self._reader:
                try:
                    line = await self._reader.readline()
                    if not line:
                        logging.warning("Stratum connection closed by remote pool.")
                        self.status = "DISCONNECTED"
                        self.disconnect_events += 1
                        self._invalidate_session("remote EOF")
                        break

                    data = line.decode("utf-8").strip()
                    if not data:
                        continue

                    try:
                        msg = json.loads(data)
                    except Exception:
                        # Previously dropped silently -- a malformed frame is
                        # a protocol fact about the peer and must leave a
                        # trace (truncated: frames can be arbitrarily large).
                        logging.warning(
                            "Stratum dropped malformed JSON frame (%d bytes): %.200s",
                            len(data),
                            data,
                        )
                        continue

                    # 1. Check for incoming server notifications
                    if "method" in msg:
                        self.parse_stratum_message(msg)

                    # 2. Check for response to client requests (by request ID)
                    elif "result" in msg or "error" in msg:
                        req_id = msg.get("id")
                        res = msg.get("result")
                        err = msg.get("error")

                        # Correlated submission response -- checked BEFORE the
                        # handshake-id shortcut so a submit verdict can never
                        # be swallowed by the authorize branch (ID-collision
                        # safety). The pending record is consumed here: a
                        # verdict resolves the entry exactly once, so a
                        # duplicated pool ACK cannot double-count.
                        rec = self._pending_futures.pop(req_id, None)
                        if rec is not None:
                            fut = rec["future"]
                            if rec.get("session_epoch") != self.session_epoch:
                                # Verdict for a share issued on a dead
                                # session: it must not be attributed to the
                                # current session's job context or counters.
                                logging.warning(
                                    f"Dropping pool response [ReqID={req_id}] from superseded "
                                    f"session (epoch {rec.get('session_epoch')} != "
                                    f"{self.session_epoch}): {msg}"
                                )
                                if not fut.done():
                                    fut.set_exception(
                                        ConnectionError(
                                            "pool response arrived for a superseded stratum session"
                                        )
                                    )
                            else:
                                accepted = (res is True) and (err is None)

                                if accepted:
                                    self.pool_accepted += 1
                                    logging.info(
                                        f"ViaBTC accepted share [ReqID={req_id}]! Total pool-accepted: {self.pool_accepted}"
                                    )
                                    if record_mining_event:
                                        record_mining_event(
                                            "share_accepted",
                                            {
                                                "job_id": rec.get("job_id") or "unknown",
                                                "extranonce1": rec.get("extranonce1"),
                                                "request_id": req_id,
                                                "pool_response": msg,
                                                "truth_class": "pool-confirmed",
                                                "difficulty": self.difficulty,
                                            },
                                        )
                                else:
                                    self.pool_rejected += 1
                                    logging.warning(
                                        f"ViaBTC rejected share [ReqID={req_id}]: {msg}"
                                    )
                                    if record_mining_event:
                                        record_mining_event(
                                            "share_rejected",
                                            {
                                                "job_id": rec.get("job_id") or "unknown",
                                                "extranonce1": rec.get("extranonce1"),
                                                "request_id": req_id,
                                                "pool_response": msg,
                                                "truth_class": "pool-rejected",
                                                "difficulty": self.difficulty,
                                            },
                                        )

                                if not fut.done():
                                    fut.set_result(accepted)

                        # Late verdict for a timed-out submission: reconcile
                        # into the counters instead of dropping it, so the
                        # client's accounting converges with the pool's own.
                        elif req_id in self._late_acks:
                            lrec = self._late_acks.pop(req_id)
                            expired = time.monotonic() > lrec.get("expires_at", 0.0)
                            stale_session = lrec.get("session_epoch") != self.session_epoch
                            if expired or stale_session:
                                logging.warning(
                                    f"Dropping late pool response [ReqID={req_id}] "
                                    f"(expired={expired}, stale_session={stale_session}): {msg}"
                                )
                            else:
                                accepted = (res is True) and (err is None)
                                self.late_acks_reconciled += 1
                                if accepted:
                                    self.pool_accepted += 1
                                    logging.info(
                                        f"ViaBTC late-accepted share [ReqID={req_id}] "
                                        f"(verdict arrived after submit timeout). "
                                        f"Total pool-accepted: {self.pool_accepted}"
                                    )
                                    if record_mining_event:
                                        record_mining_event(
                                            "share_accepted_late",
                                            {
                                                "job_id": lrec.get("job_id") or "unknown",
                                                "extranonce1": lrec.get("extranonce1"),
                                                "request_id": req_id,
                                                "pool_response": msg,
                                                "truth_class": "pool-confirmed-late",
                                                "difficulty": self.difficulty,
                                            },
                                        )
                                else:
                                    self.pool_rejected += 1
                                    logging.warning(
                                        f"ViaBTC late-rejected share [ReqID={req_id}]: {msg}"
                                    )
                                    if record_mining_event:
                                        record_mining_event(
                                            "share_rejected_late",
                                            {
                                                "job_id": lrec.get("job_id") or "unknown",
                                                "extranonce1": lrec.get("extranonce1"),
                                                "request_id": req_id,
                                                "pool_response": msg,
                                                "truth_class": "pool-rejected-late",
                                                "difficulty": self.difficulty,
                                            },
                                        )

                        # Handshake response (a stray/late authorize ACK on
                        # the live socket -- the synchronous handshake in
                        # connect() normally consumes these).
                        elif req_id == 2:
                            if res is True and err is None:
                                logging.info(
                                    f"ViaBTC Authorization confirmed: Worker '{self.worker_name}' authorized."
                                )
                            else:
                                # Previously silently ignored: an authorize
                                # failure produced no log line and no status
                                # change, so a rejected worker looked
                                # identical to an accepted one. Surface it.
                                logging.error(
                                    f"ViaBTC Authorization FAILED for worker '{self.worker_name}': {msg}"
                                )

                        elif err is not None:
                            # Unsolicited/unmatched pool error: e.g. an error
                            # for a request whose future already timed out
                            # and was popped, or a pool-level error not tied
                            # to any specific request ID. Previously dropped
                            # on the floor with no trace at all.
                            logging.warning(
                                f"ViaBTC pool reported an error not matched to a pending request (id={req_id}): {msg}"
                            )

                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logging.error(f"Error in Stratum listen loop: {e}")
                    self.status = "DISCONNECTED"
                    self.disconnect_events += 1
                    self._invalidate_session(f"listener error: {e}")
                    break
        except asyncio.CancelledError:
            # Deliberate shutdown via close()/disconnect(): exit quietly,
            # do not schedule a reconnect.
            logging.info("Stratum listen loop cancelled cleanly on shutdown.")
            raise
        finally:
            if not self._closing:
                self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        """Kick off a background reconnect-with-backoff task if one isn't already running."""
        if self._reconnecting or (self._reconnect_task and not self._reconnect_task.done()):
            return
        self._reconnecting = True
        self._reconnect_task = asyncio.create_task(self._reconnect_with_backoff())

    async def _reconnect_with_backoff(self) -> None:
        """Bounded exponential backoff retry after an unexpected disconnect.

        A dropped TCP connection or remote EOF must not silently leave the
        miner stuck forever with a stale job and no path back to the pool.
        Retries indefinitely (capped delay, not capped attempts) until either
        a connection succeeds or close()/disconnect() is called.
        """
        delay = self._reconnect_base_delay
        attempt = 0
        try:
            while not self._closing and self.status != "CONNECTED":
                attempt += 1
                self.reconnect_attempts += 1
                logging.warning(
                    f"Stratum reconnect attempt {attempt} in {delay:.1f}s (pool={self.pool_url})..."
                )
                await asyncio.sleep(delay)
                if self._closing:
                    break
                try:
                    ok = await self.connect()
                except Exception as e:
                    logging.error(f"Stratum reconnect attempt {attempt} raised: {e}")
                    ok = False
                if ok:
                    logging.info(f"Stratum reconnected successfully after {attempt} attempt(s).")
                    break
                delay = min(delay * 2.0, self._reconnect_max_delay)
        except asyncio.CancelledError:
            logging.info("Stratum reconnect loop cancelled cleanly on shutdown.")
            raise
        finally:
            self._reconnecting = False

    async def connect(
        self,
        pool_url: str = None,
        worker_name: str = None,
        connect_timeout: float = 15.0,
        handshake_timeout: float = 15.0,
    ) -> bool:
        """Perform the real Stratum handshake (ViaBTC Smart Mining & Failover profile).

        Sequence and per-field semantics are grounded in pooler/cpuminer's
        proven stratum_subscribe()/stratum_authorize() (util.c on GitHub,
        https://github.com/pooler/cpuminer):
          1. mining.subscribe (id=1) -> parse [extranonce1, extranonce2_size]
          2. mining.authorize (id=2) -> BLOCK until the id=2 response arrives
             (dispatching any interleaved mining.notify/set_difficulty
             notifications along the way), and only report CONNECTED if the
             pool actually accepted the worker/password. cpuminer's
             stratum_authorize() does exactly this synchronous wait; silently
             assuming success and moving on (the previous behavior here) means
             a rejected worker would still be reported as "connected" and the
             miner would grind on shares the pool will never accept.
        """
        # --- FAIL-CLOSED EGRESS GUARD (defence in depth) ---------------
        # connect() previously consulted no flag at all: the supervisor's
        # first tick dialled a public mining pool unconditionally, and
        # submit_share() lazily called connect() before its own approval
        # check, so even "dry" mode opened a real TCP session. Both paths
        # now terminate here unless an operator explicitly armed egress AND
        # supplied credentials.
        if not self._egress_permitted():
            self.status = "DISCONNECTED"
            return False

        if self.status == "CONNECTING":
            # A connect attempt is already in flight (e.g. the lazy reconnect
            # in submit_share() racing the background reconnect-with-backoff
            # loop). Avoid opening a second concurrent socket to the same
            # worker identity.
            logging.debug("Stratum connect() already in progress; ignoring concurrent call.")
            return False
        if self._close_in_progress:
            # A lazy connect() (e.g. submit_share's auto-reconnect) racing an
            # in-flight close() must not clear _closing and re-arm the client
            # mid-shutdown -- that produced a socket outliving close().
            logging.warning("Stratum connect() refused: client shutdown in progress.")
            return False
        # An explicit connect() call means the caller wants a live session
        # again, even if close() was called earlier.
        self._closing = False

        self.connection_attempts += 1

        target_raw = pool_url or self.pool_url
        explicit_ssl = "ssl://" in str(target_raw).lower()
        target_pool = self._clean_url(target_raw)
        target_worker = worker_name or self.worker_name

        if not target_worker:
            logging.error("No ViaBTC worker set. Expected AccountName.WorkerID, e.g. PYTHIA.001")
            self.status = "DISCONNECTED"
            return False

        pools_to_try = self._pool_priority(target_pool)

        last_error: Optional[str] = None

        for candidate_pool in pools_to_try:
            self.status = "CONNECTING"

            try:
                if ":" in candidate_pool:
                    host, port = candidate_pool.split(":")
                    port = int(port)
                else:
                    host = candidate_pool
                    port = 3333

                # Port 443 is the industry-standard "stratum+ssl" convention
                # (and is ViaBTC's documented SSL/failover port) -- attempt
                # TLS whenever the target is 443, even without an explicit
                # ssl:// scheme, and say so honestly in the log either way.
                candidate_is_ssl = explicit_ssl or (port == 443)
                logging.info(
                    f"Connecting to {candidate_pool} as {target_worker} (TLS={candidate_is_ssl})..."
                )

                t0 = time.perf_counter()
                ssl_ctx = None
                if candidate_is_ssl:
                    import ssl

                    ssl_ctx = ssl.create_default_context()
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port, ssl=ssl_ctx), timeout=connect_timeout
                )
                # Tear down the prior session's listener and socket BEFORE
                # rebinding self._reader/_writer: the previous _listen_loop
                # polls self._reader on every pass, so reassigning it while
                # that task lives lets the stale listener race this handshake
                # on the new socket, and its eventual EOF on the old socket
                # would schedule a phantom reconnect while we are live.
                prior_listen, self._listen_task = self._listen_task, None
                if prior_listen is not None and not prior_listen.done():
                    prior_listen.cancel()
                    try:
                        await prior_listen
                    except (asyncio.CancelledError, Exception):
                        pass
                prior_writer, self._writer = self._writer, None
                self._reader = None
                if prior_writer is not None:
                    try:
                        prior_writer.close()
                    except Exception:
                        pass
                self._reader = reader
                self._writer = writer
                self.pool_url = candidate_pool
                # New session: everything keyed to the prior session (job
                # context keyed to the old extranonce1, in-flight submit
                # futures, the late-ACK window) is invalidated BEFORE the
                # handshake so nothing stale can be submitted or reconciled
                # under the new session's identity.
                self._invalidate_session(f"new session to {candidate_pool}")

                # Stratum V1 Subscribe
                subscribe_msg = (
                    json.dumps(
                        {"id": 1, "method": "mining.subscribe", "params": ["hyba-pythia/1.0.0"]}
                    )
                    + "\n"
                )
                self._writer.write(subscribe_msg.encode())
                await self._writer.drain()

                # F3: a pool may legally emit mining.set_difficulty or
                # mining.notify BEFORE it answers mining.subscribe. A single
                # readline() here consumed whichever line arrived first as the
                # "subscribe response": on such a pool extranonce1 stayed at
                # its "00000000" default, every reconstructed coinbase diverged
                # from the pool's, and every share was rejected -- silently.
                # Read until the id=1 ACK actually arrives, dispatching any
                # notifications that precede it (exactly as the authorize wait
                # below already does).
                subscribed = False
                sub_deadline = time.monotonic() + handshake_timeout
                while time.monotonic() < sub_deadline:
                    remaining = max(0.1, sub_deadline - time.monotonic())
                    try:
                        sub_res = await asyncio.wait_for(reader.readline(), timeout=remaining)
                    except asyncio.TimeoutError:
                        break
                    if not sub_res:
                        break
                    try:
                        sub_data = json.loads(sub_res.decode().strip())
                    except Exception:
                        continue
                    if "method" in sub_data:
                        self.parse_stratum_message(sub_data)
                        continue
                    if sub_data.get("id") != 1:
                        continue
                    sub_result = sub_data.get("result")
                    if isinstance(sub_result, list) and len(sub_result) >= 3:
                        # [subscriptions, extranonce1, ..., extranonce2_size]
                        try:
                            self.extranonce1 = str(sub_result[1])
                            self.extranonce2_size = int(sub_result[-1])
                            subscribed = True
                            logging.info(
                                f"Extranonce1: {self.extranonce1}, "
                                f"Extranonce2 size: {self.extranonce2_size}"
                            )
                        except (TypeError, ValueError):
                            logging.warning(
                                "mining.subscribe ACK from %s had an unparsable "
                                "extranonce pair: %r",
                                candidate_pool,
                                sub_result,
                            )
                    break

                if not subscribed:
                    last_error = (
                        f"no usable mining.subscribe ACK from {candidate_pool}; "
                        f"refusing to mine with a default extranonce1"
                    )
                    logging.warning(last_error)
                    self.current_job = None
                    self.drain_jobs()
                    try:
                        writer.close()
                    except Exception:
                        pass
                    continue

                auth_msg = (
                    json.dumps(
                        {
                            "id": 2,
                            "method": "mining.authorize",
                            "params": [target_worker, self.password],
                        }
                    )
                    + "\n"
                )
                self._writer.write(auth_msg.encode())
                await self._writer.drain()

                # Block for the id=2 result, exactly like cpuminer's
                # stratum_authorize() -- dispatch any notifications that
                # arrive first instead of discarding them.
                authorized = False
                auth_deadline = time.monotonic() + handshake_timeout
                while time.monotonic() < auth_deadline:
                    remaining = max(0.1, auth_deadline - time.monotonic())
                    try:
                        auth_line = await asyncio.wait_for(reader.readline(), timeout=remaining)
                    except asyncio.TimeoutError:
                        break
                    if not auth_line:
                        break
                    try:
                        auth_data = json.loads(auth_line.decode().strip())
                    except Exception:
                        continue
                    if "method" in auth_data:
                        self.parse_stratum_message(auth_data)
                        continue
                    if auth_data.get("id") == 2:
                        authorized = bool(auth_data.get("result") is True) and auth_data.get(
                            "error"
                        ) in (None, False)
                        break

                if not authorized:
                    last_error = f"mining.authorize rejected by {candidate_pool} for worker '{target_worker}'"
                    logging.warning(last_error)
                    self.current_job = None
                    self.drain_jobs()
                    try:
                        writer.close()
                    except Exception:
                        pass
                    continue

                self.status = "CONNECTED"
                self.connected_at = time.time()
                self.latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                self.last_heartbeat = time.time()
                logging.info(
                    f"Connected to {candidate_pool} [Handshake OK - Latency {self.latency_ms}ms - Worker {target_worker} Authorized]"
                )
                # SOLVE-10MIN: state the difficulty the arithmetic supports
                # BEFORE waiting on var-diff convergence. Skipped fail-open
                # when unset/non-positive, firewalled like any other external
                # write, and never blocking on a non-cooperative pool.
                _suggested = int(os.getenv("HYBA_SUGGEST_DIFFICULTY", "0") or 0)
                if _suggested > 0:
                    await self.suggest_difficulty(_suggested)
                self._running = True

                # Start background listener — the task handle is kept on
                # self so close()/disconnect() can cancel it cleanly instead
                # of it being destroyed pending at process exit.
                self._listen_task = asyncio.create_task(self._listen_loop())

                # Wait for initial job from pool (up to 10s: a real pool can
                # take a moment to send the first mining.notify after auth).
                for _ in range(50):
                    if self.current_job and "job_id" in self.current_job:
                        logging.info(f"Initial active job ready: {self.current_job['job_id']}")
                        break
                    await asyncio.sleep(0.2)

                return True

            except Exception as e:
                last_error = f"{candidate_pool}: {type(e).__name__}: {e}"
                # Categorize network-reachability failures so the operator sees
                # a clear actionable signal (firewall/egress) rather than a
                # raw asyncio/OSError. This is the same "pool unreachable"
                # signal the Node web-tier emits.
                _errno = getattr(e, "errno", None)
                _code = getattr(e, "strerror", "") or ""
                _reach = ("ETIMEDOUT", "ECONNREFUSED", "ENETUNREACH", "EHOSTUNREACH", "timed out")
                if any(t in f"{type(e).__name__} {_code}".upper() for t in _reach) or _errno in (
                    110,
                    111,
                    101,
                    113,
                ):
                    logging.warning(
                        f"[POOL UNREACHABLE] {candidate_pool} ({type(e).__name__}) — check "
                        f"network/firewall egress to the pool; will failover/retry. ({e})"
                    )
                else:
                    logging.warning(f"Failed connecting to pool endpoint {candidate_pool}: {e}")
                stale_writer, self._writer = self._writer, None
                self._reader = None
                if stale_writer is not None:
                    try:
                        stale_writer.close()
                        wait_closed = getattr(stale_writer, "wait_closed", None)
                        if wait_closed:
                            await wait_closed()
                    except Exception as close_exc:
                        logging.debug(
                            f"Error closing failed Stratum socket for {candidate_pool}: {close_exc}"
                        )
                continue

        # No simulation fallback: a failed connection is a failed connection.
        # Surface it honestly so the Salamander supervisor owns recovery.
        logging.error(
            f"All live pool endpoints unreachable (last error: {last_error}). "
            f"SIMULATION mode removed: reporting honest connection failure to the Salamander supervisor."
        )
        self.status = "DISCONNECTED"
        self.connected_at = None
        self._running = False
        return False

    async def close(self) -> None:
        """Gracefully tear down the connection.

        Cancels and awaits the background listener task (instead of letting
        it be destroyed pending at interpreter exit — the historical "Task
        was destroyed but it is pending!" bug), cancels any in-flight
        reconnect-with-backoff attempt, fails any submissions still waiting
        on a pool ACK, and closes the socket. Idempotent: safe to call more
        than once, or on a client that was never connected.
        """
        self._closing = True
        # Held for the whole teardown so a lazy connect() racing us cannot
        # clear _closing and re-arm the client mid-shutdown.
        self._close_in_progress = True
        self._running = False

        listen_task, self._listen_task = self._listen_task, None
        if listen_task and not listen_task.done():
            listen_task.cancel()
            try:
                await listen_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logging.warning(f"Stratum listener raised while shutting down: {e}")

        reconnect_task, self._reconnect_task = self._reconnect_task, None
        if reconnect_task and not reconnect_task.done():
            reconnect_task.cancel()
            try:
                await reconnect_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logging.warning(f"Stratum reconnect loop raised while shutting down: {e}")

        # Re-assert _closing: if a reconnect attempt's connect() call
        # started running (and reset _closing = False for its own use)
        # just before being cancelled above, this guarantees close() still
        # wins the race and leaves the client in a genuinely closed state.
        self._closing = True

        # Any submission still waiting on a pool ACK will never get one now
        # — fail it honestly rather than leaving the caller's await hanging.
        for req_id, rec in list(self._pending_futures.items()):
            fut = rec["future"]
            if not fut.done():
                fut.set_exception(
                    ConnectionError("Stratum client closed while awaiting pool response")
                )
        self._pending_futures.clear()
        self._late_acks.clear()

        if self.status == "CONNECTED":
            self.disconnect_events += 1

        writer, self._writer = self._writer, None
        self._reader = None
        if writer is not None:
            try:
                writer.close()
                wait_closed = getattr(writer, "wait_closed", None)
                if wait_closed:
                    await wait_closed()
            except Exception as e:
                logging.debug(f"Error closing Stratum writer socket: {e}")

        self.status = "DISCONNECTED"
        self.connected_at = None
        self._close_in_progress = False
        logging.info(
            "Stratum client closed cleanly: listener cancelled, socket released, no orphaned tasks."
        )

    async def disconnect(self) -> None:
        """Alias for close() — some callers expect a disconnect() method."""
        await self.close()

    async def submit_share(
        self,
        job_id: str = None,
        nonce: str = None,
        ntime: str = None,
        extranonce2: str = None,
        job_epoch: int = None,
    ) -> Tuple[bool, int]:
        target_job = job_id or (
            self.current_job.get("job_id") if self.current_job else "default_job"
        )
        target_ntime = ntime or (
            self.current_job.get("ntime")
            if self.current_job
            else hex(int(time.time()))[2:].zfill(8)
        )
        target_extranonce2 = extranonce2 or self._get_next_extranonce2()
        # nonce_str is the natural/display hex form (used for logs, events,
        # and header assembly via build_stratum_block_header, which already
        # correctly little-endian-packs it). The WIRE form sent to the pool
        # over mining.submit is different -- see nonce_to_wire_hex().
        nonce_str = str(nonce).zfill(8) if nonce is not None else "00000000"

        # Job-epoch enforcement: the caller may pass the job_epoch its work
        # was computed against; otherwise derive it from the live job the
        # share names. A share computed under a retired epoch (clean_jobs)
        # or a dead session is refused before any network I/O.
        share_job_epoch = job_epoch
        if (
            share_job_epoch is None
            and self.current_job
            and self.current_job.get("job_id") == target_job
        ):
            share_job_epoch = self.current_job.get("job_epoch")
        if share_job_epoch is not None and share_job_epoch != self.job_epoch:
            self.shares_failed += 1
            self.stale_submissions_rejected += 1
            if record_mining_event:
                record_mining_event(
                    "share_submitted",
                    {
                        "job_id": target_job,
                        "nonce": nonce_str,
                        "truth_class": "stale-submission-rejected",
                        "difficulty": self.difficulty,
                        "job_epoch": share_job_epoch,
                        "active_job_epoch": self.job_epoch,
                    },
                )
            logging.warning(
                "Share submission rejected before pool write: job epoch %s is stale "
                "(active epoch %s) -- work was computed against a retired template.",
                share_job_epoch,
                self.job_epoch,
            )
            return False, UNSUBMITTED_REQUEST_ID

        if self.status != "CONNECTED":
            connected = await self.connect()
            if not connected:
                self.shares_failed += 1
                if record_mining_event:
                    record_mining_event(
                        "share_submitted",
                        {
                            "job_id": target_job,
                            "nonce": nonce_str,
                            "truth_class": "submission-failed",
                            "difficulty": self.difficulty,
                        },
                    )
                logging.error(
                    f"Share submission aborted for job '{target_job}': no live pool connection (Salamander owns recovery)."
                )
                return False, UNSUBMITTED_REQUEST_ID
            # Re-check the epoch: the lazy reconnect invalidated the session
            # and bumped job_epoch while this call was in flight.
            if share_job_epoch is not None and share_job_epoch != self.job_epoch:
                self.shares_failed += 1
                self.stale_submissions_rejected += 1
                if record_mining_event:
                    record_mining_event(
                        "share_submitted",
                        {
                            "job_id": target_job,
                            "nonce": nonce_str,
                            "truth_class": "stale-submission-rejected",
                            "difficulty": self.difficulty,
                            "job_epoch": share_job_epoch,
                            "active_job_epoch": self.job_epoch,
                        },
                    )
                logging.warning(
                    "Share submission rejected after reconnect: job epoch %s is stale "
                    "(active epoch %s).",
                    share_job_epoch,
                    self.job_epoch,
                )
                return False, UNSUBMITTED_REQUEST_ID

        active_job_id = self.current_job.get("job_id") if self.current_job else None
        if active_job_id and target_job != active_job_id:
            self.shares_failed += 1
            self.stale_submissions_rejected += 1
            if record_mining_event:
                record_mining_event(
                    "share_submitted",
                    {
                        "job_id": target_job,
                        "active_job_id": active_job_id,
                        "nonce": nonce_str,
                        "truth_class": "stale-submission-rejected",
                        "difficulty": self.difficulty,
                    },
                )
            logging.warning(
                "Share submission rejected before pool write: stale job '%s' is no longer active (active job '%s').",
                target_job,
                active_job_id,
            )
            return False, UNSUBMITTED_REQUEST_ID

        live_approved = self.is_live_submit_approved()

        if not live_approved:
            # Fall back to local validation firewall if live submission is blocked.
            # If the job did not ship a precomputed merkle_root, compute it from
            # the coinbase parts + branch exactly as mining.notify deliveries do.
            job = self.current_job or {}
            merkle_root = job.get("merkle_root")
            if merkle_root is None and job.get("coinb1") is not None:
                merkle_root = compute_stratum_merkle_root(
                    job.get("coinb1", ""),
                    self.extranonce1 or "",
                    target_extranonce2,
                    job.get("coinb2", ""),
                    job.get("merkle_branch", []),
                )
            header = build_stratum_block_header(
                job.get("version", "01000000") if job else "01000000",
                job.get("prevhash", "00" * 32) if job else "00" * 32,
                merkle_root or "00" * 32,
                target_ntime,
                job.get("nbits", "1d00ffff") if job else "1d00ffff",
                nonce_str,
            )

            accepted = self.validate_sha256d(header.hex())
            # Counter separation: a local validation verdict is firewall
            # truth, NEVER pool-confirmed truth -- it advances its own
            # counters so downstream telemetry cannot conflate the two.
            if accepted:
                self.firewall_accepted += 1
            else:
                self.firewall_rejected += 1

            if record_mining_event:
                record_mining_event(
                    "share_submitted",
                    {
                        "job_id": target_job,
                        "nonce": nonce_str,
                        "truth_class": "firewall-validation",
                        "verdict": "accepted" if accepted else "rejected",
                        "difficulty": self.difficulty,
                    },
                )
            logging.info(
                f"Firewall local validation completed for Job {target_job}. Accepted: {accepted}"
            )
            return accepted, UNSUBMITTED_REQUEST_ID

        self._submit_counter += 1
        req_id = self._submit_counter
        if req_id in _HANDSHAKE_REQUEST_IDS or req_id < _SUBMIT_ID_FLOOR:
            # Hard fail, before any wire write: a submit id in the reserved
            # handshake range would be consumed by the authorize branch of
            # the listener and the share's verdict would be lost.
            raise RuntimeError(
                f"Refusing to issue mining.submit with request id {req_id}: "
                f"collides with reserved handshake ids {sorted(_HANDSHAKE_REQUEST_IDS)}"
            )
        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        # The record carries the submission context so the pool verdict is
        # attributed to the job/extranonce/session the share was built
        # against -- not whatever current_job happens to hold when the ACK
        # arrives (a mining.notify may land between submit and ACK).
        self._pending_futures[req_id] = {
            "future": fut,
            "job_id": target_job,
            "extranonce1": self.extranonce1,
            "session_epoch": self.session_epoch,
            "job_epoch": (share_job_epoch if share_job_epoch is not None else self.job_epoch),
        }

        # Wire-format nonce: little-endian byte encoding, per the proven
        # cpuminer reference (nonce_to_wire_hex docstring). Submitting the
        # natural/display hex string here (the previous behavior) means the
        # header the pool reconstructs from our own params never matches the
        # header we validated locally -- shares would be silently rejected.
        wire_nonce = nonce_to_wire_hex(nonce_str)

        logging.info(
            f"Submitting share [ReqID={req_id}] to pool | Worker: {self.worker_name} | Job: {target_job} | Nonce: {nonce_str} (wire: {wire_nonce})"
        )

        if record_mining_event:
            record_mining_event(
                "share_submitted",
                {
                    "job_id": target_job,
                    "nonce": nonce_str,
                    "request_id": req_id,
                    "truth_class": "submission-path",
                    "difficulty": self.difficulty,
                },
            )

        try:
            submit_msg = (
                json.dumps(
                    {
                        "id": req_id,
                        "method": "mining.submit",
                        "params": [
                            self.worker_name,
                            target_job,
                            target_extranonce2,
                            target_ntime,
                            wire_nonce,
                        ],
                    }
                )
                + "\n"
            )
            # GAP-CLOSURE-001: measure the real submission leg.
            _t_send = time.perf_counter()
            if self.current_job_received_at is not None:
                self.last_submit_wait_ms = round(
                    (_t_send - self.current_job_received_at) * 1000.0, 3
                )
            self._writer.write(submit_msg.encode())
            await self._writer.drain()

            accepted = await asyncio.wait_for(fut, timeout=self.submit_timeout_seconds)
            rtt_ms = round((time.perf_counter() - _t_send) * 1000.0, 3)
            self.last_submit_rtt_ms = rtt_ms
            self.submit_rtt_samples_ms.append(rtt_ms)
            return accepted, req_id

        except asyncio.TimeoutError:
            rtt_ms = round((time.perf_counter() - _t_send) * 1000.0, 3)
            self.last_submit_rtt_ms = rtt_ms
            self.submit_rtt_samples_ms.append(rtt_ms)
            logging.warning(
                f"Submission timed out waiting for pool response [ReqID={req_id}] (rtt={rtt_ms}ms)"
            )
            # Retain the record in the late-ACK window: a verdict arriving
            # within the grace period is still reconciled into the counters
            # (and evidenced as *_late) instead of being silently dropped.
            rec = self._pending_futures.get(req_id)
            if rec is not None:
                rec["expires_at"] = time.monotonic() + self._late_ack_grace_seconds
                self._late_acks[req_id] = rec
                self._prune_late_acks()
            self.shares_timed_out += 1
            return False, req_id
        except Exception as e:
            rtt_ms = round((time.perf_counter() - _t_send) * 1000.0, 3)
            self.last_submit_rtt_ms = rtt_ms
            self.submit_rtt_samples_ms.append(rtt_ms)
            logging.error(f"Share transmission failed after {rtt_ms}ms: {e}")
            self.shares_transport_failed += 1
            return False, req_id
        finally:
            self._pending_futures.pop(req_id, None)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "pool": self.pool_url,
            "status": self.status,
            "latency": f"{self.latency_ms}ms",
            "shares_accepted": self.shares_accepted,
            "shares_rejected": self.shares_rejected,
            "shares_failed": self.shares_failed,
            # Verdict counters split by authority: pool-confirmed verdicts
            # vs local firewall validation vs no-verdict outcomes.
            "pool_accepted": self.pool_accepted,
            "pool_rejected": self.pool_rejected,
            "firewall_accepted": self.firewall_accepted,
            "firewall_rejected": self.firewall_rejected,
            "shares_timed_out": self.shares_timed_out,
            "shares_transport_failed": self.shares_transport_failed,
            "late_acks_pending": len(self._late_acks),
            "late_acks_reconciled": self.late_acks_reconciled,
            "session_epoch": self.session_epoch,
            "job_epoch": self.job_epoch,
            "client_reconnects": self.client_reconnects,
            "viabtc_source": _VIABTC_WORKER_SOURCE,
            "uptime": int(time.time() - self.connected_at) if self.connected_at else 0,
            "connection_attempts": self.connection_attempts,
            "reconnect_attempts": self.reconnect_attempts,
            "disconnect_events": self.disconnect_events,
            "jobs_received": self.jobs_received,
            "pending_submissions": len(self._pending_futures),
            "stale_submissions_rejected": self.stale_submissions_rejected,
            "reconnecting": self._reconnecting,
            # GAP-CLOSURE-001: submission-path latency facts.
            "last_submit_rtt_ms": self.last_submit_rtt_ms,
            "last_submit_wait_ms": self.last_submit_wait_ms,
            "submit_rtt_avg_ms": (
                round(sum(self.submit_rtt_samples_ms) / len(self.submit_rtt_samples_ms), 3)
                if self.submit_rtt_samples_ms
                else None
            ),
            "submit_rtt_max_ms": (
                max(self.submit_rtt_samples_ms) if self.submit_rtt_samples_ms else None
            ),
        }

    async def heartbeat(self) -> bool:
        self.last_heartbeat = time.time()
        return True

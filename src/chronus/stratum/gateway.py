"""
Chronus Single-Socket Stratum V1 Gateway & Stream Processing Engine.

Architectural Guarantees:
-------------------------
1. Single Connection Invariant: Exactly one open socket per upstream pool server.
2. Connection Generation Counter: Increments on reconnect; stale submits discarded.
3. Out-Of-Order Server Push Handlers:
   - mining.notify: Rebuilds job table keyed by job_id (keeps last N=16 jobs, respects clean_jobs).
   - mining.set_difficulty: Updates exact rational difficulty.
   - mining.set_extranonce: Updates ExtraNonce1 and ExtraNonce2 size atomically.
   - mining.set_version_mask: Updates ASICBoost version mask.
4. Robust Stream Parsing: StreamReader.readuntil(b"\n") up to 1 MiB frame limit.
"""

import asyncio
import json
import logging
import ssl
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Dict, Any, List, Optional

from chronus.stratum.bip310 import DEFAULT_CLIENT_MASK_HEX, parse_and_intersect_version_mask
from chronus.stratum.sharding import DedupLedger, WorkPartitioner
from chronus.stratum.gatekeeper import decode_nbits_target, LocalPreSubmitGatekeeper
from chronus.security.mining_policy import MiningSubmissionPolicy, parse_pool_frame
from chronus.stratum.endpoint import PoolEndpoint

logger = logging.getLogger("ChronusStratumGateway")


class StratumGateway:
    """
    Production Stratum V1 Single-Socket Client Manager.
    Manages TCP socket connection, RPC protocol handshakes, and event dispatch.
    """
    def __init__(
        self,
        host: str,
        port: int,
        worker_name: str,
        password: str = "d=131072",
        shard_count: int = 8,
        pool_timeout_sec: int = 60,
        session_idle_timeout_sec: int = 600,
        tls: bool = False,
        ssl_context: Optional["ssl.SSLContext"] = None,
    ):
        self.submission_policy = MiningSubmissionPolicy()
        self._submission_gatekeeper = LocalPreSubmitGatekeeper()
        self._submission_ledger = DedupLedger()
        self.host = host
        self.port = port
        self.worker_name = worker_name
        self.password = password
        self.shard_count = shard_count
        self.pool_timeout_sec = pool_timeout_sec
        self.session_idle_timeout_sec = session_idle_timeout_sec

        self.tls = tls
        self.ssl_context = ssl_context

        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None

        self.connection_generation: int = 0
        self.msg_id: int = 0

        # Session state
        self.pool_mask_hex: str = "00000000"
        self.extranonce1_hex: str = ""
        self.extranonce2_size: int = 4
        self.current_difficulty: Fraction = Fraction(1)
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.job_history: List[str] = []

        self.dedup_ledger = DedupLedger()
        self.partitioner = WorkPartitioner(shard_count=shard_count)
        self.is_connected: bool = False
        self.work_revision = 0
        self._job_revision = 0

    def _next_id(self) -> int:
        self.msg_id += 1
        return self.msg_id

    def reserve_id(self) -> int:
        """Reserve an RPC id so its response can be tracked before writing."""
        return self._next_id()

    async def connect(self):
        """Opens outbound TCP socket connection and increments connection generation."""
        MiningSubmissionPolicy.check_endpoint(PoolEndpoint(self.host, self.port, self.tls))
        self.submission_policy.end_connection("DISARMED_NEW_CONNECTION")
        self._submission_ledger.clear()
        self.connection_generation += 1
        self.is_connected = False
        gen = self.connection_generation
        logger.info(f"[GEN {gen}] Opening TCP socket connection to {self.host}:{self.port}...")

        # Clear stale state on new generation connection
        self.jobs.clear()
        self.job_history.clear()
        self.dedup_ledger.clear()
        self.current_difficulty = Fraction(1)
        self.extranonce1_hex = ""
        self.extranonce2_size = 4
        self.pool_mask_hex = "00000000"

        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
            self.writer = None
            self.reader = None

        # TLS is opt-in and verified; plaintext remains explicit for V1 pools.
        if self.tls:
            context = self.ssl_context or ssl.create_default_context()
            context.check_hostname = True
            context.verify_mode = ssl.CERT_REQUIRED
            connection = asyncio.open_connection(
                self.host, self.port, limit=1024 * 1024,
                ssl=context, server_hostname=self.host,
            )
        else:
            connection = asyncio.open_connection(
                self.host, self.port, limit=1024 * 1024
            )
        self.reader, self.writer = await asyncio.wait_for(
            connection, timeout=self.pool_timeout_sec,
        )
        self.is_connected = True
        logger.info(
            f"[GEN {gen}] Connected to {self.host}:{self.port} "
            f"({'TLS' if self.tls else 'cleartext'})"
        )

    def _authorize_submission(self, params, rpc_id):
        MiningSubmissionPolicy.check_endpoint(PoolEndpoint(self.host, self.port, self.tls))
        if not isinstance(params, list) or len(params) not in (5, 6) or params[0] != self.worker_name:
            raise PermissionError("Invalid mining submission contract")
        if not self.submission_policy.armed:
            raise PermissionError("Share submission is not armed")
        job = self.jobs.get(params[1])
        if job is None or job.get("generation") != self.connection_generation:
            raise PermissionError("Share references stale or unknown work")
        self._validate_hex(params[4], 8)
        valid, _, block_hash, hash_int, target_int, is_block = self._submission_gatekeeper.verify_candidate(
            job_data=job, extranonce1_hex=self.extranonce1_hex,
            extranonce2_hex=params[2], extranonce2_size=self.extranonce2_size,
            ntime_hex=params[3], nonce_int=int(params[4], 16),
            version_bits_hex=params[5] if len(params) == 6 else "00000000",
            pool_mask_hex=self.pool_mask_hex, current_difficulty=job["difficulty"],
            dedup_ledger=self._submission_ledger, active_job_ids=self.jobs,
        )
        if not valid:
            raise PermissionError("Independent pre-submit verification rejected share")
        self.submission_policy.authorize(rpc_id, {
            "job_id": job["job_id"], "generation": self.connection_generation,
            "job_revision": job.get("revision"),
            "submission_params": list(params),
            "header_sha256d": block_hash, "hash_int": str(hash_int),
            "target_int": str(target_int), "is_block_candidate": is_block,
            "independent_verification": "PASS",
        })

    async def write_rpc(self, method: str, params: List[Any],
                        rpc_id: Optional[int] = None) -> int:
        """Writes a JSON-RPC request line directly to socket without reading."""
        if not self.writer:
            raise ConnectionError("Socket is not open.")
        rpc_id = self._next_id() if rpc_id is None else rpc_id
        self.msg_id = max(self.msg_id, rpc_id)
        if method == "mining.submit":
            self._authorize_submission(params, rpc_id)
        payload_str = json.dumps({"id": rpc_id, "method": method, "params": params}) + "\n"
        self.writer.write(payload_str.encode("utf-8"))
        await asyncio.wait_for(self.writer.drain(), self.pool_timeout_sec)
        return rpc_id

    async def send_rpc(self, method: str, params: List[Any]) -> Dict[str, Any]:
        """Sends a JSON-RPC request line and reads until the response with matching ID arrives."""
        if not self.writer or not self.reader:
            raise ConnectionError("Socket is not open.")

        rpc_id = self._next_id()
        if method == "mining.submit":
            self._authorize_submission(params, rpc_id)
        payload_str = json.dumps({"id": rpc_id, "method": method, "params": params}) + "\n"
        self.writer.write(payload_str.encode("utf-8"))
        await asyncio.wait_for(self.writer.drain(), self.pool_timeout_sec)

        # Read lines until matching response id arrives; dispatch interleaved server pushes.
        # An uncorrelated response (e.g. id: null from a submit error) is logged, not dropped.
        deadline = asyncio.get_running_loop().time() + self.pool_timeout_sec
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            line = await asyncio.wait_for(self.read_line(), max(0, remaining))
            if not line:
                raise ConnectionError("Pool closed TCP socket unexpectedly.")

            try:
                response = parse_pool_frame(line)
            except (UnicodeDecodeError, ValueError) as exc:
                logger.warning(f"Malformed JSON from pool, dropping line: {exc}")
                continue

            if not isinstance(response, dict):
                logger.warning(f"Non-dict JSON payload from pool, dropping line: {response}")
                continue

            self.submission_policy.observe(response, wire_frame=line)
            if response.get("id") == rpc_id:
                return response
            if "method" in response:
                await self.handle_server_push(response)
                continue
            logger.warning("uncorrelated pool response: %s", response)

    async def read_line(self, timeout_sec=None) -> bytes:
        """Reads a single newline-delimited frame using readuntil(b'\\n') up to the 1 MiB limit.

        Wraps asyncio stream exceptions (IncompleteReadError on mid-frame EOF,
        LimitOverrunError past 1 MiB) as ConnectionError so callers only see
        protocol-level failures.
        """
        if not self.reader:
            raise ConnectionError("Socket is not open.")
        try:
            return await asyncio.wait_for(
                self.reader.readuntil(b"\n"),
                self.pool_timeout_sec if timeout_sec is None else timeout_sec,
            )
        except asyncio.IncompleteReadError as exc:
            raise ConnectionError("pool closed mid-frame") from exc
        except asyncio.LimitOverrunError as exc:
            raise ConnectionError("pool frame exceeded 1 MiB") from exc

    async def read_message(self) -> Optional[Dict[str, Any]]:
        """
        Reads next line, strips \\r, parses JSON.
        On JSON parse error, drops the line and returns None (does not disconnect).
        """
        line = await self.read_line(timeout_sec=self.session_idle_timeout_sec)
        if not line:
            return None
        try:
            msg = parse_pool_frame(line)
        except (UnicodeDecodeError, ValueError) as exc:
            logger.warning(f"Malformed JSON from pool, dropping line: {exc}")
            return None
        self.submission_policy.observe(msg, wire_frame=line)
        return msg

    async def execute_handshake(self):
        """
        Executes the 4-step Stratum V1 protocol handshake:
        1. mining.configure (ASICBoost version-rolling)
        2. mining.subscribe
        3. mining.extranonce.subscribe
        4. mining.authorize
        """
        # Step 1: mining.configure
        try:
            config_res = await self.send_rpc(
                "mining.configure",
                [["version-rolling"], {"version-rolling.mask": DEFAULT_CLIENT_MASK_HEX, "version-rolling.min-bit-count": 16}]
            )
            if (not config_res.get("error") and isinstance(config_res.get("result"), dict)
                    and config_res["result"].get("version-rolling") is True):
                srv_mask = config_res["result"].get("version-rolling.mask", "00000000")
                self.pool_mask_hex = parse_and_intersect_version_mask(srv_mask, DEFAULT_CLIENT_MASK_HEX)
                logger.info(f"[HANDSHAKE] Agreed ASICBoost version mask: {self.pool_mask_hex}")
        except (ValueError, asyncio.TimeoutError) as e:
            logger.warning(f"[HANDSHAKE] mining.configure fallback (legacy pool): {e}")
            self.pool_mask_hex = "00000000"

        # Step 2: mining.subscribe
        sub_res = await self.send_rpc("mining.subscribe", ["ChronusGateway/36.0"])
        result = sub_res.get("result", [])
        if not sub_res.get("error") and isinstance(result, list) and len(result) >= 3:
            self._validate_extranonce(result[1], result[2])
            self.extranonce1_hex = result[1]
            self.extranonce2_size = int(result[2])
            logger.info(f"[HANDSHAKE] ExtraNonce1={self.extranonce1_hex}, ExtraNonce2_Size={self.extranonce2_size}")
        else:
            raise ValueError(f"Invalid mining.subscribe result payload: {sub_res}")

        # Step 3: mining.extranonce.subscribe (optional extension)
        try:
            await asyncio.wait_for(self.send_rpc("mining.extranonce.subscribe", []), timeout=2.0)
            logger.info("[HANDSHAKE] mining.extranonce.subscribe registered")
        except asyncio.TimeoutError as e:
            logger.warning(f"[HANDSHAKE] mining.extranonce.subscribe skipped: {e}")

        # Step 4: mining.authorize
        auth_res = await asyncio.wait_for(self.send_rpc("mining.authorize", [self.worker_name, self.password]), timeout=5.0)
        if auth_res.get("result") is True and not auth_res.get("error"):
            logger.info(f"[HANDSHAKE] Authorized worker '{self.worker_name}' successfully.")
        else:
            raise PermissionError(f"Authorization failed for worker '{self.worker_name}': {auth_res.get('error')}")

    async def handle_server_push(self, msg: Dict[str, Any]):
        """Dispatches out-of-order server push messages."""
        method = msg.get("method")
        params = msg.get("params", [])
        if not isinstance(params, list):
            logger.warning("Pool push params not an array, dropping message: %s", msg)
            return

        if method == "mining.set_difficulty":
            if params:
                try:
                    difficulty = self._parse_difficulty(params[0])
                except (ValueError, TypeError) as exc:
                    # Invalid input must not destroy an otherwise healthy session.
                    logger.error("[PUSH INVALID] Bad difficulty %r: %s", params[0], exc)
                else:
                    self.current_difficulty = difficulty
                    logger.info(f"[PUSH] Set difficulty: {self.current_difficulty}")

        elif method == "mining.set_extranonce":
            if len(params) >= 2:
                try:
                    self._validate_extranonce(params[0], params[1])
                except (ValueError, TypeError) as exc:
                    logger.error("[PUSH INVALID] Bad extranonce parameters %r: %s", params[:2], exc)
                else:
                    self.extranonce1_hex = params[0]
                    self.extranonce2_size = int(params[1])
                    self.jobs.clear()
                    self.job_history.clear()
                    self.dedup_ledger.clear()
                    self.work_revision += 1
                    logger.info(f"[PUSH] Updated ExtraNonce1={self.extranonce1_hex}, Size={self.extranonce2_size}")

        elif method == "mining.set_version_mask":
            if params:
                try:
                    self._validate_hex(params[0], 8)
                    mask = parse_and_intersect_version_mask(params[0], DEFAULT_CLIENT_MASK_HEX)
                except (ValueError, TypeError) as exc:
                    logger.error("[PUSH INVALID] Bad version mask %r: %s", params[0], exc)
                else:
                    self.pool_mask_hex = mask
                    self.work_revision += 1
                    logger.info(f"[PUSH] Updated version mask: {self.pool_mask_hex}")

        elif method == "mining.notify":
            self._process_notify(params)

    def _process_notify(self, params: List[Any]):
        """Parses and validates mining.notify parameters fail-closed."""
        if len(params) != 9:
            logger.error("[PUSH INVALID] mining.notify requires 9 params. Dropping message.")
            return

        try:
            if not isinstance(params[0], str) or not params[0]:
                raise ValueError("Invalid job ID")
            for index, width in ((1, 64), (2, None), (3, None), (5, 8), (6, 8), (7, 8)):
                self._validate_hex(params[index], width)
            if not isinstance(params[4], list) or not isinstance(params[8], bool):
                raise ValueError("Invalid branches or clean_jobs")
            for branch in params[4]:
                self._validate_hex(branch, 64)
            decode_nbits_target(params[6])
        except (ValueError, TypeError):
            logger.error("[PUSH INVALID] Malformed mining.notify. Dropping message.")
            return

        job_id = str(params[0])
        prevhash_hex = str(params[1])
        coinb1_hex = str(params[2])
        coinb2_hex = str(params[3])
        merkle_branches = list(params[4])
        version_hex = str(params[5])
        nbits_hex = str(params[6])
        ntime_hex = str(params[7])
        clean_jobs = bool(params[8]) if len(params) > 8 else True

        if len(prevhash_hex) != 64:
            logger.error(f"[PUSH INVALID] PrevHash must be 64 hex chars, got {len(prevhash_hex)}. Dropping.")
            return

        if clean_jobs:
            self.jobs.clear()
            self.job_history.clear()
            self.dedup_ledger.clear()
            self.work_revision += 1
        self._job_revision += 1

        job_data = {
            "job_id": job_id,
            "prevhash_hex": prevhash_hex,
            "coinb1_hex": coinb1_hex,
            "coinb2_hex": coinb2_hex,
            "merkle_branches": merkle_branches,
            "version_hex": version_hex,
            "nbits_hex": nbits_hex,
            "ntime_hex": ntime_hex,
            "generation": self.connection_generation,
            "revision": self._job_revision,
            "difficulty": self.current_difficulty,
        }

        previous = self.jobs.get(job_id)
        header_fields = (
            "prevhash_hex", "coinb1_hex", "coinb2_hex",
            "nbits_hex",
        )
        if previous is not None and (
            any(previous[field].lower() != job_data[field].lower() for field in header_fields)
            or ((int(previous["version_hex"], 16) ^ int(version_hex, 16))
                & ~int(self.pool_mask_hex, 16)) != 0
            or [branch.lower() for branch in previous["merkle_branches"]]
            != [branch.lower() for branch in merkle_branches]
        ):
            # This ID now names a different header. Identical notifications
            # still retain their duplicate protection, as do other active jobs.
            self.dedup_ledger.discard_job(job_id)

        self.jobs[job_id] = job_data
        if job_id in self.job_history:
            self.job_history.remove(job_id)
        self.job_history.append(job_id)
        if len(self.job_history) > 16:
            oldest = self.job_history.pop(0)
            self.jobs.pop(oldest, None)
            self.dedup_ledger.discard_job(oldest)

        logger.info(f"[PUSH] Registered Job ID: {job_id} (Clean={clean_jobs}, Active Jobs={len(self.jobs)})")

    @staticmethod
    def _parse_difficulty(value):
        # Bound the decimal representation before Fraction materializes 10**exp.
        text = str(value)
        if len(text) > 128:
            raise ValueError("Pool difficulty representation is too long")
        try:
            decimal = Decimal(text)
        except InvalidOperation as exc:
            raise ValueError("Invalid pool difficulty") from exc
        if (not decimal.is_finite() or decimal <= 0
                or len(decimal.as_tuple().digits) > 64
                or abs(decimal.as_tuple().exponent) > 128):
            raise ValueError("Pool difficulty exceeds positive bounded decimal format")
        return Fraction(decimal)

    @staticmethod
    def _validate_hex(value, width=None):
        if (not isinstance(value, str) or len(value) % 2
                or (width is not None and len(value) != width)
                or any(c not in "0123456789abcdefABCDEF" for c in value)):
            raise ValueError("Invalid hexadecimal field")

    @classmethod
    def _validate_extranonce(cls, extranonce1, size):
        cls._validate_hex(extranonce1)
        if type(size) is not int or not 1 <= size <= 32:
            raise ValueError("ExtraNonce2 size must be between 1 and 32 bytes")

    async def close(self):
        """Close the socket even when durable shutdown evidence cannot be written."""
        try:
            self.submission_policy.end_connection("DISARMED_CONNECTION_CLOSED")
        finally:
            self.is_connected = False
            if self.writer:
                self.writer.close()
                try:
                    await self.writer.wait_closed()
                except Exception:
                    pass
            self.writer = None
            self.reader = None

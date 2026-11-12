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
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Dict, Any, List, Optional

from chronus.stratum.bip310 import DEFAULT_CLIENT_MASK_HEX, parse_and_intersect_version_mask
from chronus.stratum.sharding import DedupLedger, WorkPartitioner
from chronus.stratum.gatekeeper import decode_nbits_target

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
    ):
        self.host = host
        self.port = port
        self.worker_name = worker_name
        self.password = password
        self.shard_count = shard_count
        self.pool_timeout_sec = pool_timeout_sec
        self.session_idle_timeout_sec = session_idle_timeout_sec

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

    async def connect(self):
        """Opens outbound TCP socket connection and increments connection generation."""
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

        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port, limit=1024 * 1024),
            timeout=self.pool_timeout_sec,
        )
        self.is_connected = True
        logger.info(f"[GEN {gen}] Connected successfully to {self.host}:{self.port}")

    async def write_rpc(self, method: str, params: List[Any]) -> int:
        """Writes a JSON-RPC request line directly to socket without reading."""
        if not self.writer:
            raise ConnectionError("Socket is not open.")
        rpc_id = self._next_id()
        payload_str = json.dumps({"id": rpc_id, "method": method, "params": params}) + "\n"
        self.writer.write(payload_str.encode("utf-8"))
        await asyncio.wait_for(self.writer.drain(), self.pool_timeout_sec)
        return rpc_id

    async def send_rpc(self, method: str, params: List[Any]) -> Dict[str, Any]:
        """Sends a JSON-RPC request line and reads until the response with matching ID arrives."""
        if not self.writer or not self.reader:
            raise ConnectionError("Socket is not open.")

        rpc_id = self._next_id()
        payload_str = json.dumps({"id": rpc_id, "method": method, "params": params}) + "\n"
        self.writer.write(payload_str.encode("utf-8"))
        await asyncio.wait_for(self.writer.drain(), self.pool_timeout_sec)

        # Read lines until matching response id arrives; dispatch interleaved server pushes
        deadline = asyncio.get_running_loop().time() + self.pool_timeout_sec
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            line = await asyncio.wait_for(self.read_line(), max(0, remaining))
            if not line:
                raise ConnectionError("Pool closed TCP socket unexpectedly.")

            line_str = line.decode("utf-8", errors="replace").replace("\r", "").strip()
            if not line_str:
                continue

            try:
                response = json.loads(line_str, parse_float=Decimal)
            except json.JSONDecodeError as exc:
                logger.warning(f"Malformed JSON from pool, dropping line: {exc}")
                continue

            if not isinstance(response, dict):
                logger.warning(f"Non-dict JSON payload from pool, dropping line: {response}")
                continue

            if response.get("id") == rpc_id:
                return response
            elif "method" in response or response.get("id") is None:
                await self.handle_server_push(response)

    async def read_line(self, timeout_sec=None) -> bytes:
        """Reads a single newline-delimited frame using readuntil(b'\\n') up to the 1 MiB limit."""
        if not self.reader:
            raise ConnectionError("Socket is not open.")
        return await asyncio.wait_for(
            self.reader.readuntil(b"\n"),
            self.pool_timeout_sec if timeout_sec is None else timeout_sec,
        )

    async def read_message(self) -> Optional[Dict[str, Any]]:
        """
        Reads next line, strips \\r, parses JSON.
        On JSON parse error, drops the line and returns None (does not disconnect).
        """
        line = await self.read_line(timeout_sec=self.session_idle_timeout_sec)
        if not line:
            return None
        line_str = line.decode("utf-8", errors="replace").replace("\r", "").strip()
        if not line_str:
            return None
        try:
            msg = json.loads(line_str, parse_float=Decimal)
            return msg if isinstance(msg, dict) else None
        except json.JSONDecodeError as exc:
            logger.warning(f"Malformed JSON from pool, dropping line: {exc}")
            return None

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
        except ValueError as e:
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
            raise ValueError("Pool push params must be an array")

        if method == "mining.set_difficulty":
            if params:
                difficulty = self._parse_difficulty(params[0])
                self.current_difficulty = difficulty
                logger.info(f"[PUSH] Set difficulty: {self.current_difficulty}")

        elif method == "mining.set_extranonce":
            if len(params) >= 2:
                self._validate_extranonce(params[0], params[1])
                self.extranonce1_hex = params[0]
                self.extranonce2_size = int(params[1])
                self.jobs.clear()
                self.job_history.clear()
                self.dedup_ledger.clear()
                self.work_revision += 1
                logger.info(f"[PUSH] Updated ExtraNonce1={self.extranonce1_hex}, Size={self.extranonce2_size}")

        elif method == "mining.set_version_mask":
            if params:
                self.pool_mask_hex = parse_and_intersect_version_mask(params[0], DEFAULT_CLIENT_MASK_HEX)
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

        self.jobs[job_id] = job_data
        if job_id in self.job_history:
            self.job_history.remove(job_id)
        self.job_history.append(job_id)
        if len(self.job_history) > 16:
            oldest = self.job_history.pop(0)
            self.jobs.pop(oldest, None)

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
        """Closes outbound socket stream cleanly."""
        self.is_connected = False
        if self.writer:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass
        self.writer = None
        self.reader = None

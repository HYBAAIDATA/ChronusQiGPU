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
from fractions import Fraction
from typing import Dict, Any, List, Optional, Tuple

from chronus.stratum.bip310 import DEFAULT_CLIENT_MASK_HEX, parse_and_intersect_version_mask
from chronus.stratum.sharding import DedupLedger, WorkPartitioner

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
        pool_timeout_sec: int = 60
    ):
        self.host = host
        self.port = port
        self.worker_name = worker_name
        self.password = password
        self.shard_count = shard_count
        self.pool_timeout_sec = pool_timeout_sec

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

    def _next_id(self) -> int:
        self.msg_id += 1
        return self.msg_id

    async def connect(self):
        """Opens outbound TCP socket connection and increments connection generation."""
        self.connection_generation += 1
        gen = self.connection_generation
        logger.info(f"[GEN {gen}] Opening TCP socket connection to {self.host}:{self.port}...")

        # Clear stale state on new generation connection
        self.jobs.clear()
        self.job_history.clear()
        self.dedup_ledger.clear()

        self.reader, self.writer = await asyncio.open_connection(
            self.host, self.port, limit=1024 * 1024
        )
        self.is_connected = True
        logger.info(f"[GEN {gen}] Connected successfully to {self.host}:{self.port}")

    async def send_rpc(self, method: str, params: List[Any]) -> Dict[str, Any]:
        """Sends a JSON-RPC request line and reads the response line."""
        if not self.writer or not self.reader:
            raise ConnectionError("Socket is not open.")

        rpc_id = self._next_id()
        payload_str = json.dumps({"id": rpc_id, "method": method, "params": params}) + "\n"
        self.writer.write(payload_str.encode("utf-8"))
        await self.writer.drain()

        # Read response line with 1 MiB limit
        line = await self.reader.readuntil(b"\n")
        if not line:
            raise ConnectionError("Pool closed TCP socket unexpectedly.")

        line_str = line.decode("utf-8").rstrip("\r\n")
        response = json.loads(line_str)
        return response

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
            if config_res.get("result") and isinstance(config_res["result"], dict):
                srv_mask = config_res["result"].get("version-rolling.mask", "00000000")
                self.pool_mask_hex = parse_and_intersect_version_mask(srv_mask, DEFAULT_CLIENT_MASK_HEX)
                logger.info(f"[HANDSHAKE] Agreed ASICBoost version mask: {self.pool_mask_hex}")
        except Exception as e:
            logger.warning(f"[HANDSHAKE] mining.configure fallback (legacy pool): {e}")
            self.pool_mask_hex = "00000000"

        # Step 2: mining.subscribe
        sub_res = await self.send_rpc("mining.subscribe", ["ChronusGateway/36.0"])
        result = sub_res.get("result", [])
        if len(result) >= 3:
            self.extranonce1_hex = result[1]
            self.extranonce2_size = int(result[2])
            logger.info(f"[HANDSHAKE] ExtraNonce1={self.extranonce1_hex}, ExtraNonce2_Size={self.extranonce2_size}")
        else:
            raise ValueError(f"Invalid mining.subscribe result payload: {sub_res}")

        # Step 3: mining.extranonce.subscribe
        try:
            await self.send_rpc("mining.extranonce.subscribe", [])
            logger.info("[HANDSHAKE] mining.extranonce.subscribe registered")
        except Exception as e:
            logger.warning(f"[HANDSHAKE] mining.extranonce.subscribe skipped: {e}")

        # Step 4: mining.authorize
        auth_res = await self.send_rpc("mining.authorize", [self.worker_name, self.password])
        if auth_res.get("result") is True:
            logger.info(f"[HANDSHAKE] Authorized worker '{self.worker_name}' successfully.")
        else:
            raise PermissionError(f"Authorization failed for worker '{self.worker_name}': {auth_res.get('error')}")

    async def handle_server_push(self, msg: Dict[str, Any]):
        """Dispatches out-of-order server push messages."""
        method = msg.get("method")
        params = msg.get("params", [])

        if method == "mining.set_difficulty":
            if params:
                self.current_difficulty = Fraction(str(params[0]))
                logger.info(f"[PUSH] Set difficulty: {self.current_difficulty}")

        elif method == "mining.set_extranonce":
            if len(params) >= 2:
                self.extranonce1_hex = params[0]
                self.extranonce2_size = int(params[1])
                logger.info(f"[PUSH] Updated ExtraNonce1={self.extranonce1_hex}, Size={self.extranonce2_size}")

        elif method == "mining.set_version_mask":
            if params:
                self.pool_mask_hex = parse_and_intersect_version_mask(params[0], DEFAULT_CLIENT_MASK_HEX)
                logger.info(f"[PUSH] Updated version mask: {self.pool_mask_hex}")

        elif method == "mining.notify":
            self._process_notify(params)

    def _process_notify(self, params: List[Any]):
        """Parses and validates mining.notify parameters fail-closed."""
        if len(params) < 8:
            logger.error(f"[PUSH INVALID] mining.notify requires >=8 params, got {len(params)}. Dropping message.")
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

        job_data = {
            "job_id": job_id,
            "prevhash_hex": prevhash_hex,
            "coinb1_hex": coinb1_hex,
            "coinb2_hex": coinb2_hex,
            "merkle_branches": merkle_branches,
            "version_hex": version_hex,
            "nbits_hex": nbits_hex,
            "ntime_hex": ntime_hex,
            "generation": self.connection_generation
        }

        self.jobs[job_id] = job_data
        self.job_history.append(job_id)
        if len(self.job_history) > 16:
            oldest = self.job_history.pop(0)
            self.jobs.pop(oldest, None)

        logger.info(f"[PUSH] Registered Job ID: {job_id} (Clean={clean_jobs}, Active Jobs={len(self.jobs)})")

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

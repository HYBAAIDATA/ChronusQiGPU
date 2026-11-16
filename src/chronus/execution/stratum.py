"""Compatibility adapter for the historical execution.stratum API.

Canonical header math lives in chronus.stratum.endian_engine and transport in
chronus.stratum.gateway. This module preserves old imports without maintaining
a second implementation of either concern.
"""

from __future__ import annotations

import asyncio
from fractions import Fraction

from chronus.stratum.endian_engine import (
    DIFF1_TARGET,
    StratumJob,
    StratumSession,
    build_coinbase,
    build_header_prefix,
    difficulty_to_target,
    merkle_root,
    sha256d,
)
from chronus.stratum.gateway import StratumGateway


class StratumError(RuntimeError):
    """Pool protocol error (transport failure or rejected RPC)."""


def build_header(
    job: StratumJob, extranonce2: bytes, session: StratumSession, nonce: int
) -> bytes:
    """Build the canonical 76-byte prefix and append a validated LE nonce."""
    if not 0 <= nonce < 1 << 32:
        raise ValueError("nonce must be an unsigned 32-bit integer")
    return build_header_prefix(job, extranonce2, session) + nonce.to_bytes(4, "little")


class StratumV1Client:
    """Small compatibility facade over StratumGateway for legacy callers."""

    def __init__(self, host: str, port: int, user: str, password: str):
        if not host:
            raise ValueError("host is required")
        if not 1 <= port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if not user:
            raise ValueError("user is required")
        self.user = user
        self.gateway = StratumGateway(host, port, user, password)
        self._delivered_jobs: set[tuple[str, int]] = set()

    def _registered_job(self) -> tuple[StratumJob, Fraction] | None:
        """Return work consumed during the handshake before reading again."""
        for job_id in self.gateway.job_history:
            job = self.gateway.jobs.get(job_id)
            if job is None:
                continue
            marker = (job_id, job.get("revision", 0))
            if marker in self._delivered_jobs:
                continue
            self._delivered_jobs.add(marker)
            params = [
                job_id, job["prevhash_hex"], job["coinb1_hex"], job["coinb2_hex"],
                job["merkle_branches"], job["version_hex"], job["nbits_hex"],
                job["ntime_hex"], True,
            ]
            return StratumJob.from_notify(params), job["difficulty"]
        return None

    async def connect(self) -> StratumSession:
        try:
            await self.gateway.connect()
            await self.gateway.execute_handshake()
        except (OSError, asyncio.TimeoutError, ConnectionError, PermissionError) as exc:
            await self.gateway.close()
            raise StratumError(f"connect/authorize failed: {exc}") from exc
        return StratumSession(
            extranonce1=bytes.fromhex(self.gateway.extranonce1_hex),
            extranonce2_size=self.gateway.extranonce2_size,
            difficulty=self.gateway.current_difficulty,
        )

    async def next_job(self) -> tuple[StratumJob, Fraction]:
        registered = self._registered_job()
        if registered is not None:
            return registered
        while True:
            message = await self.gateway.read_message()
            if message is None:
                continue
            if "method" not in message:
                continue
            method = message.get("method")
            await self.gateway.handle_server_push(message)
            if method == "mining.notify":
                registered = self._registered_job()
                if registered is not None:
                    return registered

    async def submit(self, job: StratumJob, extranonce2: bytes, nonce: int) -> bool:
        if not 0 <= nonce < 1 << 32:
            raise ValueError("nonce must be an unsigned 32-bit integer")
        response = await self.gateway.send_rpc(
            "mining.submit",
            [self.user, job.job_id, extranonce2.hex(), job.ntime, f"{nonce:08x}"],
        )
        if response.get("error"):
            raise StratumError(f"submit rejected: {response['error']}")
        return response.get("result") is True

    async def close(self) -> None:
        await self.gateway.close()


__all__ = [
    "DIFF1_TARGET", "StratumError", "StratumJob", "StratumSession",
    "StratumV1Client", "build_coinbase", "build_header", "build_header_prefix",
    "difficulty_to_target", "merkle_root", "sha256d",
]
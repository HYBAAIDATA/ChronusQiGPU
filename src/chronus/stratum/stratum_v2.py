"""
Stratum V2 protocol client with dynamic target calculation and auto-failover.

This module provides a substrate-agnostic Stratum V2 client that can be used
with any async transport. It does not contain any GPU or hardware-specific
code.

Usage example::

    client = StratumV2PoolClient(
        "stratum.example.com:443",
        ["stratum2.example.com:443", "stratum3.example.com:443"],
    )

    # ... set up transport, then call connect_and_listen ...
"""

import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


class StratumV2PoolClient:
    """
    Asynchronous Stratum V2 pool client with auto-failover.

    Parameters
    ----------
    primary_endpoint : str
        The first (primary) pool endpoint to connect to.
    failover_endpoints : list[str]
        Ordered list of backup endpoints to attempt if the primary fails.
    on_message : callable, optional
        Callback invoked for each decoded JSON message (other than the
        special job/target messages).
    """

    def __init__(
        self,
        primary_endpoint: str,
        failover_endpoints: List[str],
        on_message: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> None:
        self.primary_endpoint = primary_endpoint
        self.failover_endpoints = list(failover_endpoints)
        self.active_endpoint = primary_endpoint
        self.current_template: Dict[str, Any] = {}
        self.target: Optional[int] = None
        self._on_message = on_message or (lambda msg: None)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    async def connect_and_listen(self) -> None:
        """
        Continuously connect to the active pool and listen for messages.

        The loop survives connection failures by rotating to the next
        endpoint in the failover list.
        """
        failover_pool = list(self.failover_endpoints)
        while True:
            try:
                logger.info(
                    "Connecting to Stratum V2 pool: %s ...", self.active_endpoint
                )
                await self._handshake()
                await self._subscribe_job_declarations()

                async for message in self._stream_messages():
                    msg_type = message.get("type")
                    if msg_type == "NewMiningJob":
                        self._on_new_job(message)
                    elif msg_type == "SetNewTarget":
                        self._handle_set_new_target(message)
                    else:
                        await self._on_message(message)

            except (ConnectionError, TimeoutError, OSError) as exc:
                logger.error(
                    "Connection lost to %s: %s",
                    self.active_endpoint,
                    exc,
                )
                self._trigger_auto_failover(failover_pool)
                await asyncio.sleep(1.0)

    # ------------------------------------------------------------------
    # Transport stubs – concrete implementations provide real I/O.
    # ------------------------------------------------------------------
    async def _handshake(self) -> None:
        """
        Perform the Stratum V2 noise handshake.

        Placeholder – no cryptographic work is performed here.
        """
        logger.info(
            "Noise handshake with %s (stub: simulated success)",
            self.active_endpoint,
        )

    async def _subscribe_job_declarations(self) -> None:
        """
        Subscribe to mining job declarations.

        Placeholder – no real subscription logic here.
        """
        logger.info("Subscribed to job declarations (stub)")

    async def _stream_messages(self) -> AsyncIterator[Dict[str, Any]]:
        """
        Asynchronously yield decoded JSON messages from the pool.

        This iterator yields example messages for demonstration and then
        stops.  Concrete implementations should read from the actual
        transport and decode each line as JSON.

        Yields
        ------
        dict
            Decoded JSON message.
        """
        sample_messages = [
            {"type": "NewMiningJob", "job_id": "job-0001"},
            {"type": "SetNewTarget", "bits": "1d00ffff"},
            {"type": "KeepAlive"},
        ]
        for msg in sample_messages:
            yield msg

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------
    def _on_new_job(self, message: Dict[str, Any]) -> None:
        """
        Record a newly announced mining job.

        Parameters
        ----------
        message : dict
            Decoded JSON message containing at least ``job_id`` and other
            job fields.
        """
        self.current_template = message
        logger.info("Received new mining job: %s", message.get("job_id"))

    def _handle_set_new_target(self, message: Dict[str, Any]) -> None:
        """
        Update the current difficulty target from a ``SetNewTarget`` message.

        Parameters
        ----------
        message : dict
            Decoded JSON message containing the compact ``bits`` field.
        """
        bits = message.get("bits")
        if bits is None:
            logger.warning(
                "SetNewTarget message missing 'bits' field; ignoring."
            )
            return
        self.target = self.bits_to_target(bits)
        logger.info("Target updated to %#x", self.target)

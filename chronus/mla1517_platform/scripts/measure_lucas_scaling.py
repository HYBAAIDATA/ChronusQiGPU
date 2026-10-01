#!/usr/bin/env python3
"""Measure real GPU-to-pool share acceptance across the MLA1517 ladder.

This is a live integration harness, not a benchmark simulator.  It refuses to
start without all of the following:

* a real OpenCL device and the exact MLA1517 ladder executor;
* a caller-supplied pool adapter that constructs consensus-valid work from a
  current Stratum job and an exact device result;
* explicit live-submission approval and pool credentials; and
* at least one pool-accepted share per rung.

A Lucas/Pisot recurrence result is not intrinsically a Bitcoin block-header
nonce.  Standard Stratum pools validate their own header and SHA-256d target.
Consequently, ``--adapter module:factory`` is mandatory.  The adapter is the
only component allowed to map an exact rung result into protocol-specific
``mining.submit`` parameters; no fabricated nonce, timestamp, job id, or
``accepted`` response is permitted here.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import importlib
import json
import logging
import os
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from chronus.mla1517.scaling import ExactScaleResult, LUCAS_PISOT_LADDER, OpenCLLadderExecutor

LOG = logging.getLogger("chronus.mla1517.live_scaling")
DIFF1_TARGET = int("00000000FFFF0000000000000000000000000000000000000000000000000000", 16)


class LiveMeasurementError(RuntimeError):
    """The live measurement cannot produce an admissible empirical result."""


@dataclass(frozen=True)
class PoolEndpoint:
    host: str
    port: int
    name: str


@dataclass(frozen=True)
class StratumJob:
    job_id: str
    params: tuple[Any, ...]
    received_ns: int


@dataclass(frozen=True)
class StratumSession:
    worker: str
    extranonce1: str
    extranonce2_size: int
    difficulty: Decimal | None
    target: int | None


class StratumAdapter(Protocol):
    """External, algorithm-specific consensus adapter contract.

    ``build_candidates`` must construct complete, pool-valid submission
    parameters.  Its output is submitted unchanged after the harness checks
    only shape and current-job identity.  It must not report acceptance itself.
    """

    def build_candidates(
        self,
        *,
        rung: ExactScaleResult,
        job: StratumJob,
        session: StratumSession,
        batch_size: int,
    ) -> Sequence[Sequence[Any]]: ...


def parse_endpoint(value: str, name: str) -> PoolEndpoint:
    host, separator, port_text = value.rpartition(":")
    if not separator or not host or ":" in host:
        raise ValueError(f"{name} must be HOST:PORT or [IPv6]:PORT")
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError(f"invalid port in {value!r}") from exc
    if not 1 <= port <= 65535:
        raise ValueError(f"invalid port in {value!r}")
    return PoolEndpoint(host, port, name)


def load_adapter(spec: str) -> StratumAdapter:
    """Load a real adapter factory; never substitute a default implementation."""
    if ":" not in spec:
        raise LiveMeasurementError("adapter must use module:factory syntax")
    module_name, factory_name = spec.split(":", 1)
    if not module_name or not factory_name:
        raise LiveMeasurementError("adapter must use module:factory syntax")
    try:
        factory = getattr(importlib.import_module(module_name), factory_name)
    except (ImportError, AttributeError) as exc:
        raise LiveMeasurementError(f"unable to load Stratum adapter {spec!r}") from exc
    adapter = factory()
    if not hasattr(adapter, "build_candidates"):
        raise LiveMeasurementError("adapter does not implement build_candidates")
    return adapter


def _parse_decimal(value: Any, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise LiveMeasurementError(f"invalid {field}: {value!r}") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise LiveMeasurementError(f"{field} must be finite and positive")
    return parsed


def effective_hashrate(
    accepted_shares: int,
    elapsed_ns: int,
    *,
    difficulty: Decimal | None,
    target: int | None,
) -> Fraction:
    """Return accepted-share-equivalent hashes/second as an exact fraction.

    The pool's announced share difficulty/target is mandatory.  A difficulty
    of one is never assumed.  Decimal difficulty is converted to an exact
    rational before the final measurement is emitted.
    """
    if accepted_shares < 0 or elapsed_ns <= 0:
        raise ValueError("accepted_shares must be non-negative and elapsed_ns positive")
    if difficulty is None and target is None:
        raise LiveMeasurementError("pool has not announced a share difficulty or target")
    if target is not None:
        if not 0 < target <= DIFF1_TARGET:
            raise LiveMeasurementError("announced share target is outside the valid range")
        expected_hashes = Fraction(accepted_shares * DIFF1_TARGET, target)
    else:
        assert difficulty is not None
        expected_hashes = Fraction(accepted_shares * DIFF1_TARGET, 1) / Fraction(difficulty)
    return expected_hashes * Fraction(1_000_000_000, elapsed_ns)


def format_rate(rate: Fraction) -> str:
    """Render the exact rational rate without converting it to binary float."""
    return format(Decimal(rate.numerator) / Decimal(rate.denominator), "f")


class LiveStratumV1:
    """Minimal live Stratum V1 client with job and target tracking."""

    def __init__(self, endpoint: PoolEndpoint, worker: str, password: str) -> None:
        self.endpoint = endpoint
        self.worker = worker
        self.password = password
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self._reader_task: asyncio.Task[None] | None = None
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._next_id = 1
        self._jobs: dict[str, StratumJob] = {}
        self.extranonce1: str | None = None
        self.extranonce2_size: int | None = None
        self.difficulty: Decimal | None = None
        self.target: int | None = None
        self._closed = False

    async def connect(self) -> None:
        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(self.endpoint.host, self.endpoint.port), timeout=15
        )
        self._closed = False
        self._reader_task = asyncio.create_task(self._read_loop())
        subscribed = await self.request("mining.subscribe", ["MLA1517/3.4", None])
        if not isinstance(subscribed, list) or len(subscribed) < 3:
            raise LiveMeasurementError("Stratum subscribe response lacks extranonce data")
        self.extranonce1 = str(subscribed[1])
        self.extranonce2_size = int(subscribed[2])
        authorized = await self.request("mining.authorize", [self.worker, self.password])
        if authorized is not True:
            raise LiveMeasurementError("Stratum authorization was not accepted")

    async def close(self) -> None:
        self._closed = True
        if self._reader_task:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
            self._reader_task = None
        for future in self._pending.values():
            if not future.done():
                future.set_exception(ConnectionError("Stratum client closed"))
        self._pending.clear()
        if self.writer:
            self.writer.close()
            with contextlib.suppress(Exception):
                await self.writer.wait_closed()
        self.reader = None
        self.writer = None

    async def _read_loop(self) -> None:
        assert self.reader is not None
        try:
            while not self._closed:
                line = await self.reader.readline()
                if not line:
                    raise ConnectionError("Stratum socket closed")
                message = json.loads(line)
                if not isinstance(message, Mapping):
                    raise LiveMeasurementError("Stratum message is not an object")
                if message.get("id") is not None:
                    request_id = int(message["id"])
                    future = self._pending.pop(request_id, None)
                    if future is None:
                        continue
                    if message.get("error"):
                        future.set_exception(LiveMeasurementError(str(message["error"])))
                    else:
                        future.set_result(message.get("result"))
                    continue
                method = message.get("method")
                params = message.get("params", [])
                if method == "mining.notify" and params:
                    job_id = str(params[0])
                    self._jobs[job_id] = StratumJob(job_id, tuple(params), time.time_ns())
                elif method == "mining.set_difficulty" and params:
                    self.difficulty = _parse_decimal(params[0], "share difficulty")
                    self.target = None
                elif method == "mining.set_target" and params:
                    target_hex = str(params[0]).removeprefix("0x")
                    self.target = int(target_hex, 16)
                    self.difficulty = None
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(exc)
            self._pending.clear()

    async def request(self, method: str, params: list[Any]) -> Any:
        if self.writer is None:
            raise ConnectionError("Stratum client is not connected")
        request_id = self._next_id
        self._next_id += 1
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[request_id] = future
        payload = json.dumps(
            {"id": request_id, "method": method, "params": params}, separators=(",", ":")
        )
        self.writer.write((payload + "\n").encode())
        await self.writer.drain()
        try:
            return await asyncio.wait_for(future, timeout=30)
        except asyncio.TimeoutError as exc:
            self._pending.pop(request_id, None)
            raise TimeoutError(f"Stratum request timed out: {method}") from exc

    def latest_job(self) -> StratumJob | None:
        return max(self._jobs.values(), key=lambda job: job.received_ns, default=None)

    def session(self) -> StratumSession:
        if self.extranonce1 is None or self.extranonce2_size is None:
            raise LiveMeasurementError("Stratum extranonce session is not initialized")
        return StratumSession(
            self.worker,
            self.extranonce1,
            self.extranonce2_size,
            self.difficulty,
            self.target,
        )


async def connect_with_failover(
    endpoints: Sequence[PoolEndpoint], worker: str, password: str
) -> LiveStratumV1:
    errors: list[str] = []
    for endpoint in endpoints:
        client = LiveStratumV1(endpoint, worker, password)
        try:
            await client.connect()
            return client
        except Exception as exc:
            errors.append(f"{endpoint.name}: {exc}")
            await client.close()
    raise LiveMeasurementError("all Stratum endpoints failed: " + "; ".join(errors))


async def execute_scaling_measurement(
    gpu_accelerator: OpenCLLadderExecutor,
    stratum_client: LiveStratumV1,
    adapter: StratumAdapter,
    *,
    batch_size: int,
    output_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Execute every rung on the real GPU and measure only pool acknowledgements."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    results: list[dict[str, Any]] = []
    for rung in LUCAS_PISOT_LADDER:
        job = stratum_client.latest_job()
        if job is None:
            raise LiveMeasurementError(f"no current Stratum job for rung {rung}")
        started_ns = time.perf_counter_ns()
        exact_result = gpu_accelerator.execute_rung(rung)
        session = stratum_client.session()
        payloads = list(
            adapter.build_candidates(
                rung=exact_result, job=job, session=session, batch_size=batch_size
            )
        )
        if not payloads:
            raise LiveMeasurementError(f"adapter produced no candidates for rung {rung}")
        accepted = 0
        for params in payloads:
            if not isinstance(params, Sequence) or isinstance(params, (str, bytes, bytearray)):
                raise LiveMeasurementError("adapter returned malformed mining.submit parameters")
            response = await stratum_client.request("mining.submit", list(params))
            if response is True:
                accepted += 1
        elapsed_ns = time.perf_counter_ns() - started_ns
        if accepted == 0:
            raise LiveMeasurementError(
                f"Stratum rejected every candidate for rung {rung}; measurement stopped"
            )
        rate = effective_hashrate(
            accepted,
            elapsed_ns,
            difficulty=stratum_client.difficulty,
            target=stratum_client.target,
        )
        record = {
            "rung": rung,
            "fibonacci": exact_result.fibonacci,
            "lucas": exact_result.lucas,
            "padovan": exact_result.padovan,
            "candidates_submitted": len(payloads),
            "accepted_shares": accepted,
            "elapsed_ns": elapsed_ns,
            "share_difficulty": (
                str(stratum_client.difficulty) if stratum_client.difficulty else None
            ),
            "share_target": hex(stratum_client.target) if stratum_client.target else None,
            "accepted_share_equivalent_hashrate_hps": format_rate(rate),
            "endpoint": stratum_client.endpoint.name,
            "measured_at_ns": time.time_ns(),
        }
        results.append(record)
        LOG.info("[RUNG %d] accepted=%d rate=%s H/s", rung, accepted, format_rate(rate))
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")
    return results


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="required explicit live-pool submission switch"
    )
    parser.add_argument("--adapter", default=os.getenv("MLA1517_STRATUM_ADAPTER"))
    parser.add_argument("--user", default=os.getenv("MLA1517_STRATUM_USER"))
    parser.add_argument("--password", default=os.getenv("MLA1517_STRATUM_PASSWORD"))
    parser.add_argument(
        "--primary", default=os.getenv("MLA1517_BRAIINS_ENDPOINT", "stratum.braiins.com:3333")
    )
    parser.add_argument(
        "--failover", default=os.getenv("MLA1517_VIABTC_ENDPOINT", "btc.viabtc.io:3333")
    )
    parser.add_argument(
        "--batch-size", type=int, default=int(os.getenv("MLA1517_SCALING_BATCH_SIZE", "1"))
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            os.getenv("MLA1517_SCALING_OUTPUT", "results/lucas_scaling_measurement.jsonl")
        ),
    )
    parser.add_argument("--opencl-kernel", default=os.getenv("MLA1517_OPENCL_LADDER_KERNEL"))
    return parser


async def _run(args: argparse.Namespace) -> None:
    if not args.live or os.getenv("MLA1517_ENABLE_LIVE_SUBMIT") != "1":
        raise SystemExit("live measurement requires --live and MLA1517_ENABLE_LIVE_SUBMIT=1")
    if not os.getenv("MLA1517_LIVE_APPROVAL_ID"):
        raise SystemExit("MLA1517_LIVE_APPROVAL_ID is required for external submissions")
    if not args.adapter:
        raise SystemExit(
            "--adapter or MLA1517_STRATUM_ADAPTER is required; no default mapping exists"
        )
    if not args.user or not args.password:
        raise SystemExit("Stratum credentials are required")
    adapter = load_adapter(args.adapter)
    gpu = OpenCLLadderExecutor(kernel_path=args.opencl_kernel)
    client = await connect_with_failover(
        [parse_endpoint(args.primary, "primary"), parse_endpoint(args.failover, "failover")],
        args.user,
        args.password,
    )
    try:
        await execute_scaling_measurement(
            gpu, client, adapter, batch_size=args.batch_size, output_path=args.output
        )
    finally:
        await client.close()


def main() -> None:
    args = _parser().parse_args()
    logging.basicConfig(level=os.getenv("MLA1517_LOG_LEVEL", "INFO"))
    try:
        asyncio.run(_run(args))
    except (LiveMeasurementError, ConnectionError, TimeoutError) as exc:
        LOG.error("live scaling measurement failed closed: %s", exc)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()

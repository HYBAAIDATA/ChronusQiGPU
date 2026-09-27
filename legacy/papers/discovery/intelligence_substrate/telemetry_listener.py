"""
HYBA Substrate — Stratum Telemetry Listener Component.

Provides an in-process asynchronous event bus for zero-latency dispatch of
Stratum ``mining.notify`` frames into the agentic mining orchestrator while
keeping network socket handling non-blocking.
"""

from __future__ import annotations

import asyncio
import json
import struct
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

import numpy as np
from .manifold_orchestrator import UnifiedManifoldOrchestrator

STRATUM_MAGIC = b"PULV"


@dataclass
class StratumTelemetryFrame:
    timestamp_ns: int
    purity: float
    fidelity: float
    latency_ms: float
    node_weights: Dict[str, float] = field(default_factory=dict)
    is_valid_passport: bool = True


@dataclass(frozen=True)
class StratumJobFrame:
    job_id: str
    prevhash: str
    coinb1: str
    coinb2: str
    merkle_branch: List[str]
    version: str
    nbits: str
    ntime: str
    clean_jobs: bool
    raw: Dict[str, Any]
    received_ns: int = field(default_factory=time.time_ns)


class AsyncStratumEventBus:
    """Dedicated-loop event bus that schedules mining.notify processing immediately."""

    def __init__(self, max_history: int = 1024) -> None:
        self._subscribers: List[Callable[[StratumJobFrame], Any]] = []
        self._history: Deque[StratumJobFrame] = deque(maxlen=max_history)
        self._lock = threading.RLock()
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop, name="stratum-event-bus", daemon=True
        )
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def subscribe(self, callback: Callable[[StratumJobFrame], Any]) -> None:
        with self._lock:
            self._subscribers.append(callback)

    def publish_mining_notify(self, frame: StratumJobFrame) -> None:
        with self._lock:
            self._history.append(frame)
            subscribers = list(self._subscribers)
        for callback in subscribers:
            self._loop.call_soon_threadsafe(
                lambda cb=callback: asyncio.create_task(self._invoke(cb, frame))
            )

    async def _invoke(
        self, callback: Callable[[StratumJobFrame], Any], frame: StratumJobFrame
    ) -> None:
        result = callback(frame)
        if asyncio.iscoroutine(result):
            await result

    def history_snapshot(self) -> List[StratumJobFrame]:
        with self._lock:
            return list(self._history)

    def stop(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=1.0)


class StratumTelemetryListener:
    def __init__(
        self,
        orchestrator: UnifiedManifoldOrchestrator,
        event_bus: Optional[AsyncStratumEventBus] = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.event_bus = event_bus or AsyncStratumEventBus()
        self.event_bus.subscribe(self._on_mining_notify)
        self.total_processed_frames = 0
        self.historical_jitters: Deque[float] = deque(maxlen=100)
        self.current_node_weights = {f"node_{i}": 1.0 / 32.0 for i in range(32)}
        self.latest_reports: Deque[Dict[str, Any]] = deque(maxlen=256)
        self._lock = threading.RLock()

    def parse_binary_passport(
        self, raw_bytes: bytes
    ) -> Tuple[bool, Optional[StratumTelemetryFrame]]:
        t_recv = time.time_ns()
        if len(raw_bytes) != 128 or raw_bytes[0:4] != STRATUM_MAGIC:
            return False, None
        ts_ns = struct.unpack(">Q", raw_bytes[4:12])[0]
        purity = struct.unpack(">f", raw_bytes[48:52])[0]
        fidelity = struct.unpack(">f", raw_bytes[52:56])[0]
        return True, StratumTelemetryFrame(
            ts_ns, purity, fidelity, max((t_recv - ts_ns) / 1e6, 0.0), is_valid_passport=True
        )

    def parse_mining_notify(
        self, raw_frame: bytes | str | Dict[str, Any]
    ) -> Optional[StratumJobFrame]:
        if isinstance(raw_frame, bytes):
            raw_frame = raw_frame.decode("utf-8", errors="ignore").strip()
        payload = json.loads(raw_frame) if isinstance(raw_frame, str) else raw_frame
        if payload.get("method") != "mining.notify":
            return None
        params = payload.get("params", [])
        if len(params) < 9:
            raise ValueError("mining.notify requires 9 Stratum parameters")
        return StratumJobFrame(
            job_id=str(params[0]),
            prevhash=str(params[1]),
            coinb1=str(params[2]),
            coinb2=str(params[3]),
            merkle_branch=list(params[4] or []),
            version=str(params[5]),
            nbits=str(params[6]),
            ntime=str(params[7]),
            clean_jobs=bool(params[8]),
            raw=payload,
        )

    def ingest_stratum_frame(self, raw_frame: bytes | str | Dict[str, Any]) -> bool:
        """Socket-facing fast path: parse and enqueue mining.notify without polling."""
        frame = self.parse_mining_notify(raw_frame)
        if frame is None:
            return False
        self.event_bus.publish_mining_notify(frame)
        return True

    def _on_mining_notify(self, frame: StratumJobFrame) -> None:
        telemetry = self._build_telemetry_payload(None, frame)
        report = self.orchestrator.execute_job(frame.__dict__, telemetry)
        with self._lock:
            self.total_processed_frames += 1
            self.latest_reports.append(report)

    def _build_telemetry_payload(
        self,
        parsed_frame: Optional[StratumTelemetryFrame],
        job_frame: Optional[StratumJobFrame] = None,
    ) -> Dict[str, Any]:
        if parsed_frame is None:
            latency_jitter = (
                float(np.std(self.historical_jitters))
                if len(self.historical_jitters) > 1
                else 0.005
            )
            lane_weights = dict(self.current_node_weights)
            purity = fidelity = 0.0
        else:
            self.historical_jitters.append(parsed_frame.latency_ms)
            latency_jitter = (
                float(np.std(self.historical_jitters))
                if len(self.historical_jitters) > 1
                else 0.005
            )
            for i in range(32):
                key = f"node_{i}"
                self.current_node_weights[key] *= float(
                    parsed_frame.fidelity * (1.05 if i == 31 else 0.99)
                )
            total_w = sum(self.current_node_weights.values()) or 1.0
            lane_weights = {k: v / total_w for k, v in self.current_node_weights.items()}
            self.current_node_weights.update(lane_weights)
            purity, fidelity = parsed_frame.purity, parsed_frame.fidelity
        return {
            "latency_jitter": latency_jitter,
            "lane_weights": lane_weights,
            "frame_purity": purity,
            "frame_fidelity": fidelity,
            "job_id": job_frame.job_id if job_frame else None,
            "nbits": job_frame.nbits if job_frame else None,
            "merkle_branch": job_frame.merkle_branch if job_frame else [],
            "clean_jobs": job_frame.clean_jobs if job_frame else False,
        }

    def process_network_event(
        self, raw_frame_payload: bytes, chunk_nonces: list[int]
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        success, parsed_frame = self.parse_binary_passport(raw_frame_payload)
        telemetry_payload = self._build_telemetry_payload(parsed_frame if success else None)
        telemetry_payload["system_tick_ms"] = (time.perf_counter() - t0) * 1000.0
        report = self.orchestrator.execute_mining_cycle(chunk_nonces, telemetry_payload)
        with self._lock:
            self.total_processed_frames += 1
            self.latest_reports.append(report)
        return report

    def latest_report_snapshot(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.latest_reports)

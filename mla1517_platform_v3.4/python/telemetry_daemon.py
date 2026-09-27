"""Out-of-band telemetry sidecar using native C seqlock snapshots."""

from __future__ import annotations
import asyncio
import os
from typing import Any

try:
    from fastapi import FastAPI, WebSocket
except ImportError as exc:
    raise SystemExit("Telemetry sidecar requires the optional 'telemetry' dependencies") from exc
from mla1517.telemetry_reader import TelemetryReader, TelemetrySnapshotError

app = FastAPI(title="MLA1517 Telemetry", version="3.0")
TELEMETRY_PATH = os.getenv("MLA1517_TELEMETRY_PATH", "/dev/shm/mla1517_telemetry")
CURSOR_PATH = os.getenv("MLA1517_PRIME_DB_CURSORS", "/dev/shm/primedb_cursors")
CURSOR_MAGIC, CURSOR_VERSION, CURSOR_BYTES, VERTICES = 0x50444243, 1, 256, 20
# Each dodecahedral vertex is reported from the shared cursor ABI.
MAX_STATES_PER_VERTEX = int(os.getenv("MLA1517_PRIME_DB_MAX_STATES", "16777216"))
try:
    _reader = TelemetryReader(TELEMETRY_PATH)
except (OSError, TelemetrySnapshotError):
    _reader = None


def _read_cursors() -> dict[str, dict[str, Any]]:
    result = {f"node_{i}": {"states_locked": 0, "saturation_pct": 0.0} for i in range(VERTICES)}
    try:
        for _ in range(1000):
            data0 = open(CURSOR_PATH, "rb").read(CURSOR_BYTES)
            if (
                len(data0) != CURSOR_BYTES
                or int.from_bytes(data0[0:4], "little") != CURSOR_MAGIC
                or int.from_bytes(data0[4:8], "little") != CURSOR_VERSION
            ):
                return result
            seq0 = int.from_bytes(data0[8:16], "little")
            if seq0 & 1:
                continue
            data1 = open(CURSOR_PATH, "rb").read(CURSOR_BYTES)
            if seq0 != int.from_bytes(data1[8:16], "little"):
                continue
            for i in range(VERTICES):
                count = int.from_bytes(data1[64 + i * 8 : 72 + i * 8], "little")
                result[f"node_{i}"] = {
                    "states_locked": count,
                    "saturation_pct": round(
                        min(count / max(MAX_STATES_PER_VERTEX, 1), 1.0) * 100.0, 6
                    ),
                }
            return result
    except FileNotFoundError:
        return result
    return result


def get_telemetry_snapshot() -> dict[str, Any]:
    if _reader is None:
        current = {
            "total_tests": 0,
            "voids_found": 0,
            "shares_accepted": 0,
            "cassini_faults": [0] * 32,
            "stratum_drops": 0,
            "query_cassini_faults": 0,
            "ring_overflows": 0,
            "catastrophic_overflows": 0,
        }
    else:
        try:
            current = _reader.read()
        except TelemetrySnapshotError:
            current = {
                "total_tests": 0,
                "voids_found": 0,
                "shares_accepted": 0,
                "cassini_faults": [0] * 32,
                "stratum_drops": 0,
                "query_cassini_faults": 0,
                "ring_overflows": 0,
                "catastrophic_overflows": 0,
            }
    current["aethel_vault_status"] = _read_cursors()
    return current


@app.websocket("/ws/topology")
async def websocket_topology(websocket: WebSocket) -> None:
    await websocket.accept()
    previous = 0
    try:
        while True:
            snapshot = get_telemetry_snapshot()
            now = int(snapshot["total_tests"])
            snapshot["tests_per_second"] = max(now - previous, 0) * 10
            previous = now
            await websocket.send_json(snapshot)
            await asyncio.sleep(0.1)
    except Exception:
        await websocket.close()

"""Produce a deterministic real-OpenCL evidence bundle for the remote SHA-256d path."""

from __future__ import annotations

import hashlib
import json
import os
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict

from chronus.mla1517.remote_gpu import PROTOCOL_VERSION, RemoteGPUClient
from chronus.mla1517.remote_gpu_agent import build_server


def _digest(header: bytes, nonce: int) -> bytes:
    blob = header[:76] + struct.pack("<I", nonce & 0xFFFFFFFF)
    return hashlib.sha256(hashlib.sha256(blob).digest()).digest()


def _case(client: RemoteGPUClient, header: bytes, target: bytes, **kwargs: Any) -> Dict[str, Any]:
    request = {
        "header": header.hex(),
        "target": target.hex(),
        **kwargs,
    }
    result = client.execute_sha256d(header, target, **kwargs)
    return {"request": request, "verified_result": result.as_dict()}


def main() -> int:
    if not os.environ.get("MLA1517_REMOTE_GPU_TOKEN", "").strip():
        raise SystemExit("MLA1517_REMOTE_GPU_TOKEN is required")
    output = Path(os.environ.get("MLA1517_HARDWARE_REPORT", "results/remote_gpu_report.json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    server = build_server("127.0.0.1", 0, max_workers=4)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        client = RemoteGPUClient(endpoint, timeout=15)
        health = client.health()
        devices = [device.as_dict() for device in client.devices()]
        capable = [d for d in devices if d["capabilities"].get("sha256d_kernel")]
        if not capable:
            raise RuntimeError("no self-checked SHA-256d OpenCL device")
        device_id = capable[0]["id"]
        header = bytes(range(80))
        later_target = min(
            int.from_bytes(_digest(header, nonce), "little") for nonce in range(64)
        ).to_bytes(32, "big")
        bounded_count = int(os.environ.get("MLA1517_HARDWARE_ACCEPTANCE_WINDOW", "4096"))
        cases = {
            "first_nonce": _case(
                client, header, b"\xff" * 32, order="contiguous",
                base_nonce=0, count=64, device_id=device_id,
            ),
            "later_nonce": _case(
                client, header, later_target, order="contiguous",
                base_nonce=0, count=64, device_id=device_id,
            ),
            "miss": _case(
                client, header, b"\x00" * 32, order="contiguous",
                base_nonce=0, count=64, device_id=device_id,
            ),
            "wraparound": _case(
                client, header, b"\x00" * 32, order="contiguous",
                base_nonce=0xFFFFFFF0, count=32, device_id=device_id,
            ),
            "bounded_window": _case(
                client, header, b"\x00" * 32, order="contiguous",
                base_nonce=0, count=bounded_count, device_id=device_id,
            ),
        }
        def worker(index: int) -> tuple[str, Dict[str, Any]]:
            return f"worker_{index}", _case(
                client, header, b"\xff" * 32, order="contiguous",
                base_nonce=100, count=64, device_id=device_id,
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            concurrent = dict(pool.map(worker, range(2)))
        bundle: Dict[str, Any] = {
            "schema": "remote-gpu-hardware-acceptance-v1",
            "captured_at_ns": time.time_ns(),
            "commit_sha": os.environ.get("GITHUB_SHA"),
            "protocol": PROTOCOL_VERSION,
            "endpoint": "loopback-http",
            "health": health,
            "devices": devices,
            "selected_device_id": device_id,
            "cases": cases,
            "concurrency": concurrent,
            "bounded_window": {
                "count": bounded_count,
                "justification": (
                    "bounded CI substitute; set "
                    "MLA1517_HARDWARE_ACCEPTANCE_WINDOW=16777216 for maximum"
                ),
            },
            "non_claims": [
                "Loopback HTTP evidence does not assert network TLS provenance.",
                "hardware_provenance_verified remains false until exercised over HTTPS with HMAC.",
            ],
        }
        canonical = json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode()
        bundle["bundle_sha256"] = hashlib.sha256(canonical).hexdigest()
        output.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n")
        print(output)
    finally:
        server.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

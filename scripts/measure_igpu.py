"""Measure what the OpenCL route really sustains on this machine, in one command.

    python scripts/measure_igpu.py                # the default OpenCL device
    python scripts/measure_igpu.py --device "UHD" --repeats 5 --out igpu.json

The simulator's iGPU figures are assumptions; only the device can replace
them. This runs real SHA256d windows of several sizes on the device (the same
``BitcoinHasher`` the miner binds), after checking the device's digests
against hashlib, and fits them with the miner's own world model. It reports:

- the per-window overhead and the hash rate (``elapsed = o + hashes / H``),
- how well that line fits each measured size (``misfit``),
- whether the device slows as a window runs (``sag``),
- and each size's measured time.

The target is all zeros, so no nonce can meet it: every window is hashed in
full and nothing here is ever a share. Nothing is sent to a pool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "mla1517_platform_v3.4" / "python"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from mining.bitcoin_hasher import BitcoinHasher  # noqa: E402
from mla1517.mining.operating_policy import lucas_ladder  # noqa: E402
from mla1517.mining.world_model import RouteModel  # noqa: E402

HEADER = bytes(range(76)) + b"\x00\x00\x00\x00"
IMPOSSIBLE = bytes(32)


def self_check(hasher: BitcoinHasher, nonces=(0, 1, 0x7FFFFFFF, 0xFFFFFFFF)) -> None:
    """Refuse a device whose digests differ from hashlib's."""
    got = hasher.hash_batch(HEADER, list(nonces))
    for nonce, digest in zip(nonces, got):
        header = HEADER[:76] + nonce.to_bytes(4, "little")
        want = hashlib.sha256(hashlib.sha256(header).digest()).digest()
        if bytes(digest) != want:
            raise SystemExit(f"device digest for nonce {nonce} differs from hashlib: refused")


def measure(hasher: BitcoinHasher, sizes: list[int], repeats: int) -> dict:
    route = RouteModel(forgetting=1.0)
    base = 0
    for _ in range(repeats):
        for size in sizes:
            kernel_before = hasher.kernel_ms
            started = time.perf_counter()
            _, _, hashes = hasher.grind_target_range_chunked(HEADER, IMPOSSIBLE, base, size)
            elapsed = time.perf_counter() - started
            kernel_s = (hasher.kernel_ms - kernel_before) / 1e3
            route.observe(hashes, elapsed, kernel_s)
            base = (base + size) & 0xFFFFFFFF
    snapshot = route.snapshot()
    snapshot["measured_ms"] = {
        str(size): round(elapsed * 1e3, 4)
        for size in sizes
        if (elapsed := route.measured_elapsed(size)) is not None
    }
    return snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--device", help="a substring of the OpenCL device name")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--max-window", type=int, default=1 << 24)
    parser.add_argument("--out", type=Path, help="also write the report here as JSON")
    args = parser.parse_args(argv)

    hasher = BitcoinHasher(backend="opencl", device=args.device)
    if hasher.backend == "cpu":
        raise SystemExit(f"no OpenCL device bound: {hasher.fallback_reason}")
    self_check(hasher)
    # Whole-epoch Lucas windows from 32 lanes up, including multi-launch ones.
    sizes = [w for w in lucas_ladder(args.max_window, 32) if w >= 1024]
    report = {
        "schema": "pythia.igpu_measurement/1",
        "device": hasher.device,
        "backend": hasher.backend,
        "launch_cap": int(hasher.grind_batch),
        "repeats": args.repeats,
        "route": measure(hasher, sizes, args.repeats),
    }
    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

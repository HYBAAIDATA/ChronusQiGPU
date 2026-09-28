"""Smoke-test instrumentation: feed vault records into a file-backed register block.

A real MLA1517 (FPGA/UIO) commits 64-byte hot states into its vault using
the producer protocol in ``host/mla1517_mmio.h``: a node's sequence word is
odd while the state is written and even once it is committed. This script
follows that protocol against a *regular file* so a smoke run can exercise
the host path (poll, plan, SHA256d, evidence) without the device.

It is not a model of the device. Each record is packed in the documented
hot-state ABI (``<Q14I``): D1 is the step n, D2-D9 are Lucas numbers
L(n+1)..L(n+8) mod 2^32, D10 is the Cassini seal (-1)^n and D11 the Unix
time. Every record it logs says ``source: smoke_abi_fixture``, and it
refuses to open anything but a regular file.

    python scripts/smoke_vault_feeder.py --device state/mmio.regs --interval 0.5
"""

from __future__ import annotations

import argparse
import json
import mmap
import os
import stat
import struct
import sys
import time

VAULT_BASE = 0x1000
VAULT_STRIDE = 0x80
STATE_OFFSET = 0x08
MEMORY_NODES = 20
MAP_BYTES = 0x2000
HOT_STATE_FORMAT = "<Q14I"
MASK32 = 0xFFFFFFFF


def lucas(n: int) -> int:
    a, b = 2, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def hot_state(n: int) -> bytes:
    seal = 1 if n % 2 == 0 else -1
    words = [lucas(n + k) & MASK32 for k in range(1, 9)]
    return struct.pack(
        HOT_STATE_FORMAT, n, *words, seal & MASK32, int(time.time()) & MASK32, 0, 0, 0, 0
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--device", required=True)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument(
        "--records", type=int, default=0, help="stop after N (0 = run until killed)"
    )
    parser.add_argument("--start-step", type=int, default=15)
    args = parser.parse_args()

    if not os.path.exists(args.device):
        with open(args.device, "wb"):
            pass
    if not stat.S_ISREG(os.stat(args.device).st_mode):
        print(f"{args.device} is not a regular file; refusing to write a device", file=sys.stderr)
        return 2
    with open(args.device, "r+b") as raw:
        if os.fstat(raw.fileno()).st_size < MAP_BYTES:
            raw.truncate(MAP_BYTES)
        mapped = mmap.mmap(raw.fileno(), MAP_BYTES)
        sequences = [0] * MEMORY_NODES
        written = 0
        try:
            while args.records == 0 or written < args.records:
                node = written % MEMORY_NODES
                base = VAULT_BASE + node * VAULT_STRIDE
                step = args.start_step + written
                state = hot_state(step)
                sequences[node] += 1
                struct.pack_into("<Q", mapped, base, 2 * sequences[node] - 1)
                mapped[base + STATE_OFFSET : base + STATE_OFFSET + 64] = state
                struct.pack_into("<Q", mapped, base, 2 * sequences[node])
                mapped.flush()
                written += 1
                print(
                    json.dumps(
                        {
                            "t": round(time.time(), 3),
                            "event": "vault_commit",
                            "node": node,
                            "sequence": 2 * sequences[node],
                            "step": step,
                            "source": "smoke_abi_fixture",
                        }
                    ),
                    flush=True,
                )
                time.sleep(args.interval)
        except KeyboardInterrupt:
            pass
        finally:
            mapped.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

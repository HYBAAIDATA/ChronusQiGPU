#!/usr/bin/env python3
"""Index footprint and probe cost: prime product address vs keyed table.

Reports honestly, including where it loses. Payload is unchanged and not
measured here. This is a HYBA Data microbenchmark for claim HD-01, not a
SLA or DRAM-savings guarantee.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

POOL = 4096


def _primes(limit: int) -> list[int]:
    flags = bytearray(b"\x01") * (limit + 1)
    flags[0:2] = b"\x00\x00"
    for i in range(2, int(limit**0.5) + 1):
        if flags[i]:
            flags[i * i :: i] = bytearray(len(flags[i * i :: i]))
    return [i for i, live in enumerate(flags) if live]


PRIMES = _primes(65536)[:POOL]


def address(ids: list[int]) -> int:
    value = 1
    for index in ids:
        value *= PRIMES[index]
    return value


def measure(n: int = 200_000, per_record: int = 3, probes: int = 20_000) -> dict:
    rng = random.Random(0)
    records = [rng.sample(range(POOL), per_record) for _ in range(n)]

    prime_bytes = sum((address(row).bit_length() + 7) // 8 for row in records)
    arr_bytes = n * 8
    table = {address(row): key for key, row in enumerate(records)}
    dict_bytes = sys.getsizeof(table) + sum(
        sys.getsizeof(key) + sys.getsizeof(value) for key, value in table.items()
    )

    # Like-for-like probe: dict lookup by precomputed key vs rebuild address
    # from the same label triple then membership. Rebuild cost is real work
    # the prime index pays; do not compare dict[key] to `key in table`.
    probe_rows = records[:probes]
    probe_keys = [address(row) for row in probe_rows]

    started = time.perf_counter()
    for key in probe_keys:
        _ = table[key]
    dict_ns = (time.perf_counter() - started) / probes * 1e9

    started = time.perf_counter()
    for row in probe_rows:
        _ = address(row) in table
    prime_ns = (time.perf_counter() - started) / probes * 1e9

    return {
        "records": n,
        "labels_per_record": per_record,
        "prime_index_bytes": prime_bytes,
        "numpy_int64_bytes": arr_bytes,
        "dict_bytes": dict_bytes,
        "prime_vs_dict_ratio": round(dict_bytes / max(1, prime_bytes), 1),
        "prime_vs_numpy_ratio": round(arr_bytes / max(1, prime_bytes), 2),
        "prime_probe_ns": round(prime_ns, 1),
        "dict_probe_ns": round(dict_ns, 1),
        "address_bytes_at_4096_labels": (
            address([4095, 4094, 4093]).bit_length() + 7
        )
        // 8,
        "notes": (
            "int64 array holds one key; a prime address holds a three-label set — "
            "compare like for like. Probe times: dict uses a precomputed key; "
            "prime rebuilds the address from labels then membership-checks. "
            "Payload bytes are unchanged and not measured. HD-01 footprint "
            "ratio is storage, not probe latency."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=200_000)
    parser.add_argument("--per-record", type=int, default=3)
    parser.add_argument("--probes", type=int, default=20_000)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)
    result = measure(args.records, args.per_record, args.probes)
    for key, value in result.items():
        print(f"{key}: {value}")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""AL HARAS (HYBA Security) measurement script.

Measures the wall-clock cost of the implemented AL HARAS checks on the machine
that runs it and writes the raw results as JSON. It makes no comparison with
other products and no claim about hardware: the numbers describe this Python
implementation, on this machine, for the stated input sizes.

    python benchmarks/benchmark_al_haras_security.py --json results.json
"""

import argparse
import json
import os
import platform
import sys
import time
from fractions import Fraction
from typing import Any, Callable, Dict, List

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from chronus.security.al_haras import braids, expander, reed_solomon  # noqa: E402
from chronus.security.al_haras.receipts import ReceiptSigner, signed_receipt  # noqa: E402
from chronus.security.al_haras.sheaf import analyse_states  # noqa: E402


def _measure(fn: Callable[[], Any], iterations: int) -> Dict[str, Any]:
    samples: List[int] = []
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        fn()
        samples.append(time.perf_counter_ns() - t0)
    samples.sort()
    return {
        "iterations": iterations,
        "median_us": samples[len(samples) // 2] / 1000,
        "p95_us": samples[min(len(samples) - 1, (95 * len(samples)) // 100)] / 1000,
        "min_us": samples[0] / 1000,
    }


def sheaf_case(nodes: int, dim: int, iterations: int) -> Dict[str, Any]:
    names = [f"agent_{i}" for i in range(nodes)]
    states = {n: [i + 1 for i in range(dim)] for n in names}
    states[names[nodes // 2]] = [7 * (i + 1) for i in range(dim)]  # one disagreeing node
    edges = [(names[i], names[i + 1]) for i in range(nodes - 1)]
    result = analyse_states(states, edges=edges)
    return {
        "input": {"nodes": nodes, "stalk_dim": dim, "edges": len(edges)},
        "located_nodes": result["isolating_nodes"],
        "timing": _measure(lambda: analyse_states(states, edges=edges), iterations),
    }


def reed_solomon_case(size: int, faults: int, iterations: int) -> Dict[str, Any]:
    trace = bytes((i * 31 + 7) % 256 for i in range(size))
    envelope = reed_solomon.protect(trace)
    positions = reed_solomon.deterministic_fault_positions(trace, faults)
    corrupted = reed_solomon.inject_faults(trace, positions)
    outcome = reed_solomon.heal(corrupted, envelope)
    return {
        "input": {"trace_bytes": size, "faults": faults, "code": f"RS({envelope['n']},{envelope['k']}) over GF(257)"},
        "repaired_and_verified": outcome["integrity_verified"],
        "protect_timing": _measure(lambda: reed_solomon.protect(trace), iterations),
        "heal_timing": _measure(lambda: reed_solomon.heal(corrupted, envelope), iterations),
    }


def expander_case(q: int) -> Dict[str, Any]:
    expander.certify_paley.cache_clear()
    expander.paley_neighbours.cache_clear()
    t0 = time.perf_counter_ns()
    cert = expander.certify_paley(q)
    elapsed = time.perf_counter_ns() - t0
    return {
        "input": {"q": q},
        "is_ramanujan": cert["is_ramanujan"],
        "certificate_time_ms": elapsed / 1_000_000,
        "resilience_30_percent_removed": expander.removal_resilience(q, Fraction(3, 10)),
    }


def receipt_case(iterations: int) -> Dict[str, Any]:
    body = {"decision": "ADMIT", "payload_sha256": "0" * 64}
    rec = signed_receipt(body)
    return {
        "sign_timing": _measure(lambda: signed_receipt(body), iterations),
        "verify_timing": _measure(lambda: ReceiptSigner.verify(rec["body"], rec["signature"]), iterations),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--json", dest="json_path")
    args = parser.parse_args()
    n = max(1, args.iterations)
    results = {
        "what_this_measures": "wall-clock time of the AL HARAS Python implementation on this machine",
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "processor": platform.processor() or "not reported",
            "logical_cpus": os.cpu_count(),
        },
        "sheaf_consistency": [sheaf_case(8, 4, n), sheaf_case(32, 8, max(1, n // 4))],
        "reed_solomon_repair": [reed_solomon_case(1024, 1, n), reed_solomon_case(1024, 32, max(1, n // 4))],
        "paley_expander": expander_case(257),
        "braid_relations_time_ms": _measure(braids.verify_relations, n)["median_us"] / 1000,
        "ed25519_receipts": receipt_case(n),
    }
    text = json.dumps(results, indent=2)
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

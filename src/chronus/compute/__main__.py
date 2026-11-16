"""Local Chronus compute admission utility.

Usage:
  python -m chronus.compute --mode geometry
  python -m chronus.compute --mode exact-known-answer
  python -m chronus.compute --mode metal-known-answer
  python -m chronus.compute --mode metal-state --state-npy in.npy --output-npy out.npy

The Metal route requires physical Apple Silicon + MLX and fails closed.
Known-answer probes are NOT workload benchmarks, hardware attestations,
real Stratum mining evidence, or production qualification.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def _report(record: dict[str, object]) -> None:
    print(json.dumps(record, sort_keys=True, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chronus exact/Metal compute admission")
    parser.add_argument("--mode", required=True,
                        choices=("geometry", "exact-known-answer",
                                 "metal-known-answer", "metal-state"))
    parser.add_argument("--state-npy", type=Path)
    parser.add_argument("--output-npy", type=Path)
    args = parser.parse_args(argv)

    try:
        if args.mode == "geometry":
            from chronus.geodesic.dual_120cell import build_dual_120_cell
            from chronus.geodesic.embedding_11d import embedding_certificate
            _report({
                "classification": "EXACT_SOFTWARE_GEOMETRY_CHECK",
                "geometry": build_dual_120_cell().invariants(),
                "embedding": embedding_certificate(),
                "runtime_hardware_evidence": "UNAVAILABLE",
            })
            return 0

        from chronus.compute.quantum_evolution_igpu import iGPUQuantumEvolution
        dispatcher = iGPUQuantumEvolution()
        try:
            if args.mode == "exact-known-answer":
                stalks = [[0] * 600 for _ in range(32)]
                stalks[0][0] = 1
                result = dispatcher.laplacian_exact(stalks)
                verdict = (result["state"][0][0] == 4 and
                           sum(result["state"][0]) == 0 and
                           sum(v != 0 for row in result["state"] for v in row) == 5)
                if not verdict:
                    raise ArithmeticError("exact H4 known-answer failed")
                _report({
                    "classification": "EXACT_SOFTWARE_KNOWN_ANSWER_NOT_BENCHMARK",
                    "verdict": "PASS", "task_id": result["task_id"],
                    "measured_worker_ns": result["measured_worker_ns"],
                    "hardware_attested": False,
                })
            elif args.mode == "metal-known-answer":
                import numpy as np
                a = np.array([[1,2],[3,4]],dtype=np.float32)
                b = np.array([[4,3],[2,1]],dtype=np.float32)
                result = dispatcher.matmul_metal(a,b)
                _report({
                    "classification": "PHYSICAL_METAL_KNOWN_ANSWER_NOT_BENCHMARK",
                    "task_id": result["task_id"],
                    "measured_worker_ns": result["measured_worker_ns"],
                    "device": result["device"],
                    "host_parity": result["host_parity"],
                    "hardware_attested": False,
                })
            else:
                if args.state_npy is None or args.output_npy is None:
                    parser.error("metal-state requires --state-npy and --output-npy")
                import numpy as np
                state = np.load(args.state_npy,allow_pickle=False)
                if state.dtype != np.float32 or state.shape != (32,600):
                    raise ValueError("state file must contain finite float32 [32,600]")
                result = dispatcher.laplacian_metal(state)
                np.save(args.output_npy,result["state"],allow_pickle=False)
                _report({
                    "classification": "MEASURED_METAL_FLOAT32_LINEAR_OPERATION",
                    "input": str(args.state_npy),
                    "output": str(args.output_npy),
                    "input_sha256": result["input_sha256"],
                    "output_sha256": result["output_sha256"],
                    "measured_worker_ns": result["measured_worker_ns"],
                    "host_parity": result["host_parity"],
                    "device": result["device"],
                    "hardware_attested": False,
                    "claim_exact_quantum_evolution": False,
                })
            return 0
        finally:
            dispatcher.shutdown()
    except Exception as exc:
        _report({
            "verdict": "UNAVAILABLE_OR_FAILED",
            "classification": "NOT_PRODUCTION_QUALIFIED",
            "error_type": type(exc).__name__,
            "error": str(exc),
        })
        return 1


if __name__ == "__main__":
    sys.exit(main())

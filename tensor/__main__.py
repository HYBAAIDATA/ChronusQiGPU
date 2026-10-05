"""``python -m tensor`` — CLI over the canonical runtime.

Subcommands (all print a single JSON object to stdout):

* ``store NAME --shape MxN [--dtype float64] [--depth N] [--seed N]``
  Fold a deterministic array into resident custody.
* ``run OP NAME... [--out NAME]`` — execute a catalogue op over resident
  blocks (folded-resident path) and publish the output block + receipt.
* ``benchmark OP [--repeats N] [--size N]`` — promotion harness: lifted vs
  materialized measured against an independent reference.
* ``report`` — custody status + operator catalogue + evidence.

Custody persists between invocations via a checkpoint file
(``--store-path``, default ``.tensor_runtime.npz``) — the same
``.npz`` format ``PersistentFoldStore`` restores with content-hash
verification.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

import numpy as np

from aethel.fold_store import FoldStoreError, PersistentFoldStore

from .api import TensorRuntime
from .benchmarks import run_benchmarks
from .folded import evaluate_operator


def _parse_shape(text: str) -> tuple[int, ...]:
    dims = tuple(int(p) for p in text.lower().replace(" ", "").split("x") if p)
    if not dims or any(d <= 0 for d in dims):
        raise argparse.ArgumentTypeError(f"bad shape {text!r} (expected e.g. 8x16)")
    return dims


def _load_runtime(args: argparse.Namespace) -> TensorRuntime:
    path = Path(args.store_path)
    if path.exists():
        store = PersistentFoldStore.restore(path)
    else:
        store = PersistentFoldStore()
    return TensorRuntime(store=store)


def _save(args: argparse.Namespace, rt: TensorRuntime) -> None:
    rt.store.checkpoint(args.store_path)


def _cmd_store(args: argparse.Namespace) -> Dict[str, Any]:
    rt = _load_runtime(args)
    shape = _parse_shape(args.shape)
    rng = np.random.default_rng(args.seed)
    dtype = np.dtype(args.dtype)
    if dtype.kind == "c":
        data = rng.standard_normal(shape) + 1j * rng.standard_normal(shape)
    elif dtype.kind in "iu":
        data = rng.integers(0, 1000, size=shape)
    else:
        data = rng.standard_normal(shape)
    info = rt.store_tensor(args.name, np.asarray(data, dtype=dtype), depth=args.depth)
    _save(args, rt)
    return {"ok": True, "command": "store", **info,
            "shape": list(shape), "dtype": dtype.name, "seed": args.seed}


def _cmd_run(args: argparse.Namespace) -> Dict[str, Any]:
    rt = _load_runtime(args)
    record = rt.execute(args.operation, list(args.inputs), out=args.out)
    _save(args, rt)
    return {"ok": True, "command": "run", **record}


def _cmd_benchmark(args: argparse.Namespace) -> Dict[str, Any]:
    n = int(args.size)
    rng = np.random.default_rng(0)
    a = rng.standard_normal((n, n))
    b = rng.standard_normal((n, n))
    workloads = {
        "add": (a, b),
        "hadamard": (a, b),
        "scale": (a, np.array([1.25])),
        "fma": (a, b, np.full((n, n), 0.25)),
        "reduce_sum": (a,),
        "transpose": (a,),
        "matmul": (a, b),
        "kron": (a[:4], b[:8, : min(8, n)]),
    }
    if args.operation not in workloads:
        raise FoldStoreError(
            f"no benchmark workload for {args.operation!r}; "
            f"have {sorted(workloads)}"
        )
    evidence = evaluate_operator(
        args.operation, workloads[args.operation], repeats=args.repeats
    )
    report = run_benchmarks(
        operations=[args.operation],
        sizes=((n, n),),
        repeats=args.repeats,
    )
    return {
        "ok": True,
        "command": "benchmark",
        "size": n,
        "correct": report.all_valid,
        "promotion": dict(evidence.__dict__),
        "report": report.as_dict(),
    }


def _cmd_report(args: argparse.Namespace) -> Dict[str, Any]:
    rt = _load_runtime(args)
    return {
        "ok": True,
        "command": "report",
        "capabilities": rt.capabilities(),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tensor")
    parser.add_argument(
        "--store-path",
        default=".tensor_runtime.npz",
        help="fold-store checkpoint file (default .tensor_runtime.npz)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("store", help="fold an array into custody")
    p.add_argument("name")
    p.add_argument("--shape", required=True)
    p.add_argument("--dtype", default="float64")
    p.add_argument("--depth", type=int, default=3)
    p.add_argument("--seed", type=int, default=0)
    p.set_defaults(handler=_cmd_store)

    p = sub.add_parser("run", help="execute an op over resident blocks")
    p.add_argument("operation")
    p.add_argument("inputs", nargs="+")
    p.add_argument("--out", default=None)
    p.set_defaults(handler=_cmd_run)

    p = sub.add_parser("benchmark", help="measure lifted vs materialized")
    p.add_argument("operation")
    p.add_argument("--repeats", type=int, default=5)
    p.add_argument("--size", type=int, default=32)
    p.set_defaults(handler=_cmd_benchmark)

    p = sub.add_parser("report", help="custody + capability report")
    p.set_defaults(handler=_cmd_report)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
    except Exception as exc:  # noqa: BLE001 - CLI reports JSON errors, exit 1
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())

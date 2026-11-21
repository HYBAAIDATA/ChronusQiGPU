#!/usr/bin/env python3
"""Paired bounded reference workload: stage(0) vs folded residence.

Inputs must be a named Git-tracked byte file. Byte-derived controlled operands
are not customer workloads or fleet telemetry. Both runs execute the same
operation sequences and compare every logical output. Materializations are
counted from the real FoldLedger, not inferred from the operation registry.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import time
from fractions import Fraction
from pathlib import Path

from chronus.math.fold_ledger import FoldLedger, FoldedWords, dedup, keyed_lookup, fold_residency

ROOT = Path(__file__).resolve().parents[2]
EXPO = 1000000007
OPS = {
    "event_log": ("add", "sub", "equals", "keyed_lookup", "add", "scale", "gram_dot", "equals", "dedup", "sub"),
    "object_store": ("dedup", "keyed_lookup", "equals", "keyed_lookup", "dedup", "equals", "keyed_lookup", "dedup", "equals", "keyed_lookup", "equals"),
    "analytics": ("sort", "threshold", "topk", "sort", "threshold", "topk", "sort", "threshold", "topk", "gram_dot"),
}


def operands(raw: bytes) -> tuple[int, ...]:
    if not raw:
        raise ValueError("nonempty input required")
    padded = raw + bytes((-len(raw)) % 16)
    return tuple(int.from_bytes(padded[i:i+8], "big") for i in range(0, len(padded), 8))


def execute(words: tuple[int, ...], operations: tuple[str, ...], exponent: int) -> dict:
    ledger = FoldLedger(64).stage(exponent)
    value = FoldedWords.from_plain(ledger, words)
    other = FoldedWords.from_plain(ledger, words)
    ingress = ledger.materializations
    egress = native = 0
    observations = []
    for op in operations:
        before = ledger.materializations
        if op == "add":
            value = value.add(other)
            native += 1
        elif op == "sub":
            value = value.sub(other)
            native += 1
        elif op == "scale":
            value = value.scale(3)
            native += 1
        elif op == "equals":
            observations.append(value.equals(other))
            native += 1
        elif op == "gram_dot":
            observations.append(value.gram_dot(other))
            native += 1
        elif op == "dedup":
            observations.append(len(dedup((value, other, value))))
            native += 1
        elif op == "keyed_lookup":
            observations.append(keyed_lookup({value: 1}, value))
            native += 1
        elif op in ("sort", "threshold", "topk"):
            plain = ledger.unfold(value.words)
            if ledger.materializations != before + 1:
                raise ArithmeticError("boundary must materialize exactly once")
            egress += 1
            if op == "sort":
                plain = tuple(sorted(plain))
            elif op == "threshold":
                plain = tuple(x if x >= 1 << 63 else 0 for x in plain)
            else:
                observations.append(max(plain))
            value = FoldedWords.from_plain(ledger, plain)
            ingress += 1
        else:
            raise ValueError("unimplemented operation")
        if op not in ("sort", "threshold", "topk") and ledger.materializations != before:
            raise ArithmeticError("native operation materialized")
    before = ledger.materializations
    result = ledger.unfold(value.words)
    if ledger.materializations != before + 1:
        raise ArithmeticError("final egress must materialize exactly once")
    egress += 1
    if ingress + egress != ledger.materializations:
        raise ArithmeticError("materialization accounting mismatch")
    return {"output_sha256": hashlib.sha256(json.dumps([result, observations], separators=(",", ":")).encode()).hexdigest(),
            "native_ops": native, "operation_count": len(operations),
            "residency": str(Fraction(native, len(operations))),
            "ingress": ingress, "egress": egress, "materializations": ledger.materializations}


def campaign(raw: bytes) -> dict:
    words = operands(raw)
    results = {}
    for label, operations in OPS.items():
        rows = {}
        for mode, exponent in (("identity", 0), ("folded", EXPO)):
            start = time.perf_counter_ns()
            row = execute(words, operations, exponent)
            row["elapsed_ns"] = time.perf_counter_ns() - start
            if row["residency"] != str(fold_residency(operations)):
                raise ArithmeticError("registry/execution mismatch")
            rows[mode] = row
        if rows["identity"]["output_sha256"] != rows["folded"]["output_sha256"]:
            raise ArithmeticError("paired logical outputs differ")
        results[label] = {"operations": list(operations), "equal_output": True, **rows}
    return {"schema": "chronus.reference-residency/1", "scope": "bounded CPU reference; no customer, fleet or throughput claim",
            "platform": platform.platform(), "input_sha256": hashlib.sha256(raw).hexdigest(),
            "input_bytes": len(raw), "results": results}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    path = a.input.resolve()
    relative = path.relative_to(ROOT)
    rev = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()
    raw = subprocess.check_output(["git", "show", f"{rev}:{relative.as_posix()}"], cwd=ROOT)
    if path.read_bytes() != raw:
        raise SystemExit("input differs from committed bytes")
    if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT):
        raise SystemExit("clean tracked worktree required")
    result = campaign(raw)
    result.update(source_commit=rev, input_path=relative.as_posix())
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    a.output.parent.mkdir(parents=True, exist_ok=True)
    with a.output.open("x", encoding="utf-8") as stream:
        stream.write(encoded)
    print(encoded)
    print("artifact_sha256=" + hashlib.sha256(encoded.encode()).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

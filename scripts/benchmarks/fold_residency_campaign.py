"""PRE-REGISTERED synthetic operation-trace campaign (not customer telemetry).

Predictions: event_log high, object_store high, analytics low.
Equal-work baseline: identity fold, stage(0), same op multiset, same input
words and instrumented materializations. Candidate stage(7), 8-bit words.
Each boundary operation performs one explicit egress (unfold); final output
performs one egress. Reingress/initial encodings are separately counted.
The synthetic traces model operation classes, not complete applications.
No latency, throughput or capacity superiority is inferred.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from fractions import Fraction
from pathlib import Path

from chronus.math.fold_ledger import (
    FoldLedger, FoldedWords, OPS_BOUNDARY, OPS_FOLDED, dedup, keyed_lookup,
)

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "evidence/residency/inputs/traces.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_trace(spec, stage):
    ledger = FoldLedger(bits=8).stage(stage)
    current = FoldedWords.from_plain(ledger, spec["words"])
    other = FoldedWords.from_plain(ledger, spec["other"])
    ingress = ledger.materializations
    observations = []
    egress_counts = []
    executed = Counter()

    def egress():
        before = ledger.materializations
        plain = ledger.unfold(current.words)
        count = ledger.materializations - before
        if count != 1:
            raise RuntimeError("egress must materialize exactly once")
        egress_counts.append(count)
        return plain

    for op in spec["ops"]:
        if op not in OPS_FOLDED | OPS_BOUNDARY:
            raise ValueError("unclassified operation")
        if op == "add":
            current = current.add(other)
        elif op == "sub":
            current = current.sub(other)
        elif op == "scale":
            current = current.scale(3)
        elif op == "equals":
            observations.append(current.equals(other))
        elif op == "gram_dot":
            observations.append(current.gram_dot(other))
        elif op == "dedup":
            observations.append(len(dedup((current, other, current))))
        elif op == "keyed_lookup":
            observations.append(keyed_lookup({current: "found"}, current))
        elif op in OPS_BOUNDARY:
            plain = egress()
            if op == "sort":
                result = tuple(sorted(plain))
            elif op == "threshold":
                result = tuple(x if x >= 128 else 0 for x in plain)
            elif op == "topk":
                result = tuple(sorted(plain, reverse=True)[:2])
            elif op == "magnitude_join":
                # Exact inner join on magnitude with the committed plain input;
                # sorted matching word pairs flattened, preserving even length.
                result = tuple(x for a in plain for b in spec["other"]
                               if abs(a) == abs(b) for x in (a, b))
            else:
                raise ValueError("boundary not implemented for these traces")
            current = FoldedWords.from_plain(ledger, result)
            # Preserve shape for later folded binary operations.
            other = FoldedWords.from_plain(ledger, (0,) * len(result))
            ingress += 2
        executed[op] += 1
    output = egress()
    if ledger.materializations != ingress + sum(egress_counts):
        raise RuntimeError("materialization accounting mismatch")
    return {"output": list(output), "observations": observations,
            "op_multiset": dict(executed),
            "materializations": ledger.materializations,
            "ingress_materializations": ingress, "egress_materializations": egress_counts}


def campaign():
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT):
        raise RuntimeError("clean tracked worktree required")
    data = json.loads(DATA.read_text())
    classes = {}
    for name, spec in data["classes"].items():
        candidate, baseline = run_trace(spec, 7), run_trace(spec, 0)
        for key in ("output", "observations", "op_multiset"):
            if candidate[key] != baseline[key]:
                raise RuntimeError(f"equal-work mismatch: {name}/{key}")
        counts = candidate["op_multiset"]
        fraction = Fraction(sum(n for op, n in counts.items() if op in OPS_FOLDED),
                            sum(counts.values()))
        classes[name] = {"residency": f"{fraction.numerator}/{fraction.denominator}",
                         "prediction": spec["prediction"], "candidate": candidate,
                         "baseline": baseline, "dataset_sha256": sha(DATA)}
    return {"schema": "chronus.fold-residency/1", "source_commit": commit,
            "script_sha256": sha(Path(__file__)), "dataset_sha256": sha(DATA),
            "data_class": "committed synthetic operation traces",
            "note": "measured, not benchmarked; no speed or customer workload claim",
            "classes": classes}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "evidence/residency")
    args = parser.parse_args()
    result = campaign()
    path = args.output_dir / result["source_commit"] / "campaign.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(path)


if __name__ == "__main__":
    main()

"""Authoritative PR #104 conformance acceptance gate."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from compiler import compile_ir
from conformance.build import build
from conformance.canonical import canonical, tree_digest
from conformance.generators.isa import cases as machine_cases
from conformance.generators.semantic import generated, named
from conformance.replay import replay_all

STATUSES = {
    "PASS",
    "REJECTED_IR",
    "REJECTED_ASSEMBLY",
    "TRAP",
    "BUDGET_EXHAUSTED",
    "CONTAINER_REJECTED",
    "RESULT_MISMATCH",
    "NONDETERMINISTIC",
    "HARNESS_ERROR",
    "NOT_RUN",
}
NORMATIVE_TRAPS = {
    "IllegalOpcode",
    "MalformedEncoding",
    "Misaligned",
    "OutOfBounds",
    "InvalidSelector",
    "DivergenceOverflow",
    "BarrierDeadlock",
    "InvalidEarlyExit",
    "BudgetExhausted",
    "BinaryFormat",
}


def say(text):
    print(f"{text:60s} PASS")


def rejected(ir):
    try:
        compile_ir(ir)
    except ValueError:
        return True
    return False


def source_revision():
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise AssertionError(f"non-canonical source revision: {revision!r}")
    return revision


def main():
    subprocess.run([sys.executable, "scripts/check_chronus103.py"], cwd=ROOT, check=True)
    say("#100-#103 inherited gates")

    for n in (1, 31, 32, 33, 255, 256, 257, 1024, 4063, 4064, 4065, 4079, 4080):
        compile_ir({"schema": "chronus.ir.v0.1", "name": "v", "op": "vector_add", "dtype": "f32", "shape": {"n": n}})
    assert rejected({"schema": "chronus.ir.v0.1", "name": "v", "op": "vector_add", "dtype": "f32", "shape": {"n": 4081}})
    say("vector_add contract 1..4080; first rejection 4081")

    for op, shape in [("vector_add", {"n": 4}), ("reduce_sum_local", {"n": 4}), ("matmul_tiled", {"m": 32, "k": 32, "n": 32})]:
        assert rejected({"schema": "chronus.ir.v0.1", "name": "f64", "op": op, "dtype": "f64", "shape": shape})
    say("Float64/f64 rejection")

    for n in (1, 31, 32, 33, 255, 256):
        compile_ir({"schema": "chronus.ir.v0.1", "name": "r", "op": "reduce_sum_local", "dtype": "f32", "shape": {"n": n}})
    assert rejected({"schema": "chronus.ir.v0.1", "name": "r", "op": "reduce_sum_local", "dtype": "f32", "shape": {"n": 257}})
    say("reduce_sum_local contract 1..256; first rejection 257")

    compile_ir({"schema": "chronus.ir.v0.1", "name": "m", "op": "matmul_tiled", "dtype": "f32", "shape": {"m": 32, "k": 32, "n": 32}})
    for dims in ((31, 32, 32), (33, 32, 32), (32, 31, 32), (32, 33, 32), (32, 32, 31), (32, 32, 33)):
        assert rejected({"schema": "chronus.ir.v0.1", "name": "m", "op": "matmul_tiled", "dtype": "f32", "shape": dict(zip(("m", "k", "n"), dims))})
    say("matmul_tiled fixed shape and neighboring rejection")

    machine = machine_cases()
    ops = {case["name"][6:].upper() for case in machine if case["kind"] == "legal_opcode"}
    assert len(ops) == 20
    assert all(case["status"] in STATUSES for case in machine)
    assert all(case["trap"] is None or case["trap"] in NORMATIVE_TRAPS for case in machine)
    assert next(case for case in machine if case["name"] == "workgroup_isolation")["status"] == "PASS"
    say("ISA authority uses normative trap classes and isolation PASS")

    semantic = named() + generated()
    assert sum(x[0] == "vector_add" and x[3] == "PASS" for x in generated()) == 256
    assert sum(x[0] == "reduce_sum_local" and x[3] == "PASS" for x in generated()) == 256
    assert sum(x[0] == "matmul_tiled" and x[3] == "PASS" for x in generated()) == 128
    say("semantic named and deterministic generated breadth")

    with tempfile.TemporaryDirectory() as td:
        a = Path(td) / "a"
        b = Path(td) / "b"
        manifest_a = build(a)
        manifest_b = build(b)
        assert manifest_a == manifest_b
        assert tree_digest(a) == tree_digest(b)
        say("byte-identical corpus regeneration twice")

        committed = json.loads((ROOT / "conformance" / "corpus.json").read_text())
        assert committed == manifest_a, (
            "committed conformance/corpus.json is stale; regenerate it from the authoritative #104 builder before claiming closure"
        )
        assert manifest_a["artifact_root"] != "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
        say("committed corpus manifest binds non-empty immutable artifacts")

        raw = b"".join(path.read_bytes() for path in a.rglob("*") if path.is_file())
        assert b"/data/" not in raw and b"pickle" not in raw
        assert all(path.suffix != ".pkl" for path in a.rglob("*"))
        say("portable corpus isolation and artifact SHA-256")

        replay_a = replay_all(a)
        replay_b = replay_all(b)
        assert replay_a == replay_b
        assert tree_digest(a) == tree_digest(b)
        assert replay_a["result_count"] == manifest_a["case_count"]
        say("all corpus cases replayed against reference authority")
        say("byte-identical deterministic reference replay")

    revision = source_revision()
    closure = {
        "schema": "chronus104-closure-v2",
        "source_revision": revision,
        "base_pr": 103,
        "base_head": "16453b2e8c0c360498cb90916b39d8792c5b5dbe",
        "corpus_sha256": manifest_a["corpus_sha256"],
        "artifact_root": manifest_a["artifact_root"],
        "case_root": manifest_a["case_root"],
        "results_root": replay_a["results_root"],
        "case_counts": {"semantic": len(semantic), "machine": len(machine), "total": manifest_a["case_count"]},
        "semantic_pass": sum(x[3] == "PASS" for x in semantic),
        "semantic_rejected": sum(x[3] == "REJECTED_IR" for x in semantic),
        "machine_pass": sum(x["status"] == "PASS" for x in machine),
        "trap_count": sum(x["status"] in ("TRAP", "BUDGET_EXHAUSTED") for x in machine),
        "container_rejections": sum(x["status"] == "CONTAINER_REJECTED" for x in machine),
        "deterministic_regeneration": True,
        "deterministic_replay": True,
        "reference_replay": replay_a,
        "normative_traps": sorted(NORMATIVE_TRAPS),
        "f64_rejected": True,
        "vector_add_max_n": 4080,
        "vector_add_first_rejected_n": 4081,
        "status": "PASS",
        "CI_STATUS": "NOT_REPORTED",
    }
    out = ROOT / "artifacts"
    out.mkdir(exist_ok=True)
    data = canonical(closure)
    (out / "chronus104-closure.json").write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    (out / "chronus104-sha256sums.txt").write_text(f"{digest}  chronus104-closure.json\n")
    (out / "chronus104-corpus-root.json").write_text(json.dumps(manifest_a, sort_keys=True, separators=(",", ":")))
    print("Chronus #104 conformance suite acceptance: PASS")
    print("CI STATUS: NOT REPORTED")


if __name__ == "__main__":
    main()

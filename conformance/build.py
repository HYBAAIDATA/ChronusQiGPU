from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from compiler import compile_ir
from conformance.canonical import canonical, case_id, sha, tree_digest
from conformance.generators.inputs import values
from conformance.generators.isa import cases as isa_cases
from conformance.generators.semantic import generated, named
from conformance.machine import machine_fixture
from conformance.oracle import matmul_tiled, reduce_sum_local, vector_add


def put(root, kind, data):
    digest = sha(data)
    path = root / "artifacts" / kind / digest
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return digest


def _generator_source_digest() -> str:
    paths = [
        ROOT / "conformance" / "build.py",
        ROOT / "conformance" / "canonical.py",
        ROOT / "conformance" / "generators" / "semantic.py",
        ROOT / "conformance" / "generators" / "inputs.py",
        ROOT / "conformance" / "generators" / "isa.py",
        ROOT / "conformance" / "machine.py",
        ROOT / "conformance" / "oracle.py",
        ROOT / "conformance" / "machine_cases.json",
        ROOT / "conformance" / "trap_taxonomy.json",
        *sorted((ROOT / "conformance" / "schema").glob("*.json")),
    ]
    framed = bytearray()
    for path in paths:
        rel = path.relative_to(ROOT).as_posix().encode()
        data = path.read_bytes()
        framed += len(rel).to_bytes(4, "little") + rel
        framed += len(data).to_bytes(8, "little") + data
    return sha(bytes(framed))


def _not_run(case):
    return {
        "schema": "chronus.conformance.result.v1",
        "case_id": case["case_id"],
        "runner": "not-run",
        "runner_sha256": None,
        "actual_sha256": None,
        "trace_sha256": None,
        "actual_status": "NOT_RUN",
        "actual_trap": None,
        "passed": False,
    }


def build(root):
    root = Path(root)
    shutil.rmtree(root, ignore_errors=True)
    (root / "cases" / "semantic").mkdir(parents=True)
    (root / "cases" / "isa").mkdir(parents=True)
    (root / "results" / "reference").mkdir(parents=True)
    records = []

    for machine in isa_cases():
        fixture = machine_fixture(machine)
        input_sha = put(root, "inputs", canonical(fixture["spec"]))
        executable_sha = (
            put(root, "binaries", fixture["blob"])
            if fixture["blob"] is not None
            else None
        )
        expected_sha = put(
            root,
            "expected",
            canonical(
                {
                    "schema": "chronus.machine.expected.v1",
                    "status": machine["status"],
                    "trap": machine["trap"],
                    "dump": fixture["spec"].get("expected_dump"),
                }
            ),
        )
        rec = {
            "schema": "chronus.conformance.case.v1",
            "case_id": "",
            "class": "isa",
            "operation": machine["name"],
            "seed": machine.get("seed"),
            "ir_sha256": None,
            "input_sha256": input_sha,
            "executable_sha256": executable_sha,
            "expected_sha256": expected_sha,
            "expected_status": machine["status"],
            "expected_trap": machine["trap"],
            "limits": {
                "instruction_budget": int(fixture["spec"].get("budget") or 10_000_000),
                "barrier_budget": 4096,
            },
        }
        rec["case_id"] = case_id(rec)
        (root / "cases" / "isa" / f'{rec["case_id"][7:]}.json').write_bytes(canonical(rec))
        records.append(rec)
        (root / "results" / "reference" / f'{rec["case_id"][7:]}.json').write_bytes(canonical(_not_run(rec)))

    for op, seed, ir, status in named() + generated():
        ir_bytes = canonical(ir)
        ir_sha = put(root, "ir", ir_bytes)
        input_sha = executable_sha = expected_sha = None
        if status == "PASS":
            compiled = compile_ir(ir)
            executable_sha = put(root, "binaries", compiled.container)
            if op == "vector_add":
                n = ir["shape"]["n"]
                a = values(seed, n)
                b = values(seed + 1, n)
                raw = a.tobytes() + b.tobytes()
                out = vector_add(a, b)
            elif op == "reduce_sum_local":
                n = ir["shape"]["n"]
                a = values(seed, n)
                raw = a.tobytes()
                out = reduce_sum_local(a)
            else:
                a = values(seed, 1024).reshape(32, 32)
                b = values(seed + 1, 1024).reshape(32, 32)
                raw = a.tobytes() + b.tobytes()
                out = matmul_tiled(a, b)
            input_sha = put(root, "inputs", raw)
            expected_sha = put(root, "expected", out.astype("<f4").tobytes())
        rec = {
            "schema": "chronus.conformance.case.v1",
            "case_id": "",
            "class": "semantic",
            "operation": op,
            "seed": seed,
            "ir_sha256": ir_sha,
            "input_sha256": input_sha,
            "executable_sha256": executable_sha,
            "expected_sha256": expected_sha,
            "expected_status": status,
            "expected_trap": None,
            "limits": {
                "instruction_budget": 10_000_000,
                "barrier_budget": 4096,
            },
        }
        rec["case_id"] = case_id(rec)
        (root / "cases" / "semantic" / f'{rec["case_id"][7:]}.json').write_bytes(canonical(rec))
        records.append(rec)
        (root / "results" / "reference" / f'{rec["case_id"][7:]}.json').write_bytes(canonical(_not_run(rec)))

    seed_digest = sha(canonical([x[1] for x in named() + generated()]))
    case_root = sha(canonical(sorted(record["case_id"] for record in records)))
    artifact_root = tree_digest(root / "artifacts")
    manifest = {
        "schema": "chronus.conformance.corpus.v1",
        "generator_version": "1.1.0",
        "generator_source_sha256": _generator_source_digest(),
        "isa_version": "chronus1-1.0",
        "abi_version": "chronus-abi-1",
        "container_version": "chronus-1.1",
        "compiler_version": "chronus-subset-v0.1",
        "assembler_version": "chronus-asm-1",
        "canonicalization_version": "canonical-json-v1",
        "seed_set_digest": seed_digest,
        "case_count": len(records),
        "artifact_root": artifact_root,
        "case_root": case_root,
        "corpus_sha256": "0" * 64,
        "byte_order": "little",
        "float_representation": "IEEE-754 binary32",
    }
    manifest["corpus_sha256"] = sha(canonical({**manifest, "corpus_sha256": None}))
    (root / "corpus.json").write_bytes(canonical(manifest))
    return manifest

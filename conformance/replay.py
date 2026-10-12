"""Executable replay for the Chronus #104 immutable conformance corpus."""
from __future__ import annotations

import json
import struct
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from compiler import compile_ir
from conformance.canonical import canonical, sha, tree_digest
from conformance.oracle import POLICY

ROOT = Path(__file__).resolve().parents[1]


def _chronus_path(name: str) -> Path:
    """Source-tree location of a Chronus component (relocated under chronus/),
    falling back to the flat layout used by installed wheels."""
    nested = ROOT / "chronus" / name
    return nested if nested.exists() else ROOT / name


def _artifact(root: Path, kind: str, digest: str) -> Path:
    path = root / "artifacts" / kind / digest
    if not path.is_file():
        raise AssertionError(f"missing content-addressed artifact: {kind}/{digest}")
    if sha(path.read_bytes()) != digest:
        raise AssertionError(f"artifact digest mismatch: {kind}/{digest}")
    return path


def _find_emulator(name: str) -> Path:
    build = _chronus_path("emulator") / "build"
    candidates = [
        build / name,
        build / f"{name}.exe",
        build / "Release" / name,
        build / "Release" / f"{name}.exe",
        build / "Debug" / name,
        build / "Debug" / f"{name}.exe",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise AssertionError(f"reference emulator artifact not found: {name}")


def _store_bytes(root: Path, family: str, data: bytes, suffix: str) -> str:
    digest = sha(data)
    path = root / "results" / family / f"{digest}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise AssertionError(f"content-address collision at {path}")
    path.write_bytes(data)
    return digest


def _write_result(root: Path, result: dict) -> None:
    path = root / "results" / "reference" / f"{result['case_id'][7:]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(result))


def _cli_command(cli: Path, exe: Path, spec: dict, td: Path) -> list[str]:
    dispatch = spec["dispatch"]
    cmd = [
        str(cli),
        "--load",
        str(exe),
        "--global",
        ",".join(map(str, dispatch["global"])),
        "--local",
        ",".join(map(str, dispatch["local"])),
        "--memory",
        str(spec["memory"]),
        "--budget",
        str(spec["budget"]),
    ]
    for index, upload in enumerate(spec.get("uploads", [])):
        data = bytes.fromhex(upload["hex"])
        path = td / f"upload-{index}.bin"
        path.write_bytes(data)
        cmd += ["--upload", f"{path}@{upload['address']}"]
    if spec.get("dump") is not None:
        address, words = spec["dump"]
        cmd += ["--dump", f"{address}:{words}"]
    return cmd


def _trap_from_stderr(stderr: str) -> str:
    text = stderr.lower()
    if "reserved chronus-1 opcode" in text:
        return "IllegalOpcode"
    if any(token in text for token in ("non-zero reserved", "base field must be zero", "selector must be zero")):
        return "MalformedEncoding"
    if any(token in text for token in ("invalid barrier encoding", "invalid builtin selector", "zero dispatch dimension", "work-group exceeds chronus-1")):
        return "InvalidSelector"
    if "unaligned 32-bit memory access" in text:
        return "Misaligned"
    if any(token in text for token in ("outside committed range", "pc outside code")):
        return "OutOfBounds"
    if "divergence stack overflow" in text:
        return "DivergenceOverflow"
    if "work-item exited before a peer barrier" in text:
        return "InvalidEarlyExit"
    if "work-group cannot make progress" in text:
        return "BarrierDeadlock"
    if "instruction budget exhausted" in text:
        return "BudgetExhausted"
    if any(
        token in text
        for token in (
            "bad chrn header",
            "unsupported binary layout",
            "container checksum mismatch",
            "missing metadata",
            "metadata reserved field",
            "truncated symbol",
            "invalid symbol",
            "duplicate symbol",
            "truncated reconvergence",
            "invalid reconvergence",
            "trailing metadata",
            "missing or surplus reconvergence",
            "cannot open executable",
            "committed vram below binary requirement",
        )
    ):
        return "BinaryFormat"
    raise AssertionError(f"unclassified reference trap: {stderr.strip()!r}")


def _semantic_inputs(compiled, ir: dict, raw: bytes) -> tuple[list[tuple[int, bytes]], tuple[int, int]]:
    op = ir["op"]
    if op == "vector_add":
        n = int(ir["shape"]["n"])
        width = 4 * n
        if len(raw) != width * 2:
            raise AssertionError("vector_add input artifact size mismatch")
        one = np.asarray([1.0], dtype="<f4").tobytes()
        return [
            (compiled.memory["A"], raw[:width]),
            (compiled.memory["B"], raw[width:]),
            (compiled.memory["ONE"], one),
        ], (compiled.memory["C"], n)
    if op == "reduce_sum_local":
        n = int(ir["shape"]["n"])
        if len(raw) != 4 * n:
            raise AssertionError("reduce_sum_local input artifact size mismatch")
        one = np.asarray([1.0], dtype="<f4").tobytes()
        return [
            (compiled.memory["A"], raw),
            (compiled.memory["ONE"], one),
        ], (compiled.memory["OUT"], 1)
    if op == "matmul_tiled":
        width = 4 * 1024
        if len(raw) != width * 2:
            raise AssertionError("matmul_tiled input artifact size mismatch")
        return [
            (compiled.memory["A"], raw[:width]),
            (compiled.memory["B"], raw[width:]),
        ], (compiled.memory["C"], 1024)
    raise AssertionError(f"unsupported semantic operation: {op}")


def _semantic_compare(op: str, actual: bytes, expected: bytes) -> None:
    policy = POLICY[op]
    if policy in {"exact", "ordered-exact"}:
        if actual != expected:
            raise AssertionError(f"{op} output differs from independent oracle")
        return
    if policy == "max_abs_error<=1e-5":
        got = np.frombuffer(actual, dtype="<f4")
        ref = np.frombuffer(expected, dtype="<f4")
        if got.shape != ref.shape:
            raise AssertionError("matmul output shape mismatch")
        error = float(np.max(np.abs(got - ref))) if got.size else 0.0
        if not np.isfinite(error) or error > 1e-5:
            raise AssertionError(f"matmul oracle error {error} exceeds 1e-5")
        return
    raise AssertionError(f"unknown oracle policy {policy!r}")


def replay_semantic(root: Path, cli: Path | None = None) -> dict:
    root = Path(root)
    cli = cli or _find_emulator("chronus-emu")
    cli_sha = sha(cli.read_bytes())
    compiler_sha = tree_digest(_chronus_path("compiler"))
    passed = rejected = 0

    for case_path in sorted((root / "cases" / "semantic").glob("*.json")):
        case = json.loads(case_path.read_text())
        ir = json.loads(_artifact(root, "ir", case["ir_sha256"]).read_text())

        if case["expected_status"] == "REJECTED_IR":
            try:
                compile_ir(ir)
            except ValueError:
                _write_result(
                    root,
                    {
                        "schema": "chronus.conformance.result.v1",
                        "case_id": case["case_id"],
                        "runner": "chronus-subset-compiler-v0.1",
                        "runner_sha256": compiler_sha,
                        "actual_sha256": None,
                        "trace_sha256": None,
                        "actual_status": "REJECTED_IR",
                        "actual_trap": None,
                        "passed": True,
                    },
                )
                rejected += 1
                continue
            raise AssertionError(f"{case['case_id']} expected REJECTED_IR but compiled")

        if case["expected_status"] != "PASS":
            raise AssertionError(f"semantic case {case['case_id']} has unsupported expected status {case['expected_status']}")

        compiled = compile_ir(ir)
        if sha(compiled.container) != case["executable_sha256"]:
            raise AssertionError(f"{case['case_id']} compiler output drifted from corpus binary")
        executable = _artifact(root, "binaries", case["executable_sha256"])
        raw_input = _artifact(root, "inputs", case["input_sha256"]).read_bytes()
        expected = _artifact(root, "expected", case["expected_sha256"]).read_bytes()

        with tempfile.TemporaryDirectory() as tmp:
            td = Path(tmp)
            exe = td / "case.chronus"
            exe.write_bytes(executable.read_bytes())
            uploads, dump = _semantic_inputs(compiled, ir, raw_input)
            spec = {
                "dispatch": {"global": list(compiled.geometry.global_size), "local": list(compiled.geometry.local_size)},
                "memory": compiled.memory["required_bytes"],
                "budget": int(case["limits"]["instruction_budget"]),
                "uploads": [{"address": address, "hex": data.hex()} for address, data in uploads],
                "dump": [dump[0], dump[1]],
            }
            proc = subprocess.run(_cli_command(cli, exe, spec, td), cwd=ROOT, capture_output=True, text=True)
        if proc.returncode != 0:
            raise AssertionError(f"{case['case_id']} reference emulator failed: rc={proc.returncode} stderr={proc.stderr.strip()!r}")
        payload = json.loads(proc.stdout)
        words = payload.get("dump")
        if not isinstance(words, list):
            raise AssertionError("reference emulator did not return dump words")
        actual = struct.pack(f"<{len(words)}I", *[int(x) & 0xFFFFFFFF for x in words])
        _semantic_compare(ir["op"], actual, expected)

        actual_sha = _store_bytes(root, "actual", actual, ".bin")
        trace = canonical(
            {
                "case_id": case["case_id"],
                "lane_instructions": payload.get("lane_instructions"),
                "scheduler_steps": payload.get("scheduler_steps"),
                "trace_hash": payload.get("trace_hash"),
                "work_groups": payload.get("work_groups"),
            }
        )
        trace_sha = _store_bytes(root, "traces", trace, ".json")
        _write_result(
            root,
            {
                "schema": "chronus.conformance.result.v1",
                "case_id": case["case_id"],
                "runner": "chronus-reference-emulator-v1",
                "runner_sha256": cli_sha,
                "actual_sha256": actual_sha,
                "trace_sha256": trace_sha,
                "actual_status": "PASS",
                "actual_trap": None,
                "passed": True,
            },
        )
        passed += 1

    return {"pass": passed, "rejected_ir": rejected}


def replay_machine(root: Path, cli: Path | None = None) -> dict:
    root = Path(root)
    cli = cli or _find_emulator("chronus-emu")
    cli_sha = sha(cli.read_bytes())
    suite = _find_emulator("chronus-emulator-tests")
    suite_source = _chronus_path("emulator") / "tests" / "test_emulator.cpp"
    suite_source_text = suite_source.read_text(errors="ignore")
    suite_sha = sha(suite.read_bytes() + suite_source.read_bytes())
    counts: dict[str, int] = {}

    for case_path in sorted((root / "cases" / "isa").glob("*.json")):
        case = json.loads(case_path.read_text())
        spec = json.loads(_artifact(root, "inputs", case["input_sha256"]).read_text())
        expected = json.loads(_artifact(root, "expected", case["expected_sha256"]).read_text())
        if expected["status"] != case["expected_status"] or expected["trap"] != case["expected_trap"]:
            raise AssertionError(f"{case['case_id']} expected artifact disagrees with case")

        if spec["mode"] == "emulator-test-suite":
            test = spec["test"]
            if f"static void {test}(" not in suite_source_text or f"{test}();" not in suite_source_text:
                raise AssertionError(f"reference suite does not invoke {test}")
            proc = subprocess.run([str(suite)], cwd=ROOT, capture_output=True, text=True)
            if proc.returncode != 0:
                raise AssertionError(f"reference emulator test suite failed: {proc.stderr.strip()}")
            actual_status = case["expected_status"]
            actual_trap = case["expected_trap"]
            actual_record = {"test": test, "suite_stdout": proc.stdout.strip(), "status": actual_status, "trap": actual_trap}
            runner = "chronus-reference-emulator-tests"
            runner_sha = suite_sha
        else:
            executable = _artifact(root, "binaries", case["executable_sha256"])
            with tempfile.TemporaryDirectory() as tmp:
                td = Path(tmp)
                exe = td / "case.chronus"
                exe.write_bytes(executable.read_bytes())
                proc = subprocess.run(_cli_command(cli, exe, spec, td), cwd=ROOT, capture_output=True, text=True)
            if proc.returncode == 0:
                payload = json.loads(proc.stdout)
                if spec.get("expected_dump") is not None and payload.get("dump") != spec["expected_dump"]:
                    raise AssertionError(f"{case['case_id']} dump mismatch: {payload.get('dump')} != {spec['expected_dump']}")
                actual_status = "PASS"
                actual_trap = None
                actual_record = {"status": actual_status, "trap": actual_trap, "payload": payload}
            elif proc.returncode == 2:
                actual_trap = _trap_from_stderr(proc.stderr)
                if actual_trap == "BudgetExhausted":
                    actual_status = "BUDGET_EXHAUSTED"
                elif actual_trap == "BinaryFormat":
                    actual_status = "CONTAINER_REJECTED"
                else:
                    actual_status = "TRAP"
                actual_record = {"status": actual_status, "trap": actual_trap, "stderr": proc.stderr.strip()}
            else:
                actual_status = "HARNESS_ERROR"
                actual_trap = None
                actual_record = {
                    "status": actual_status,
                    "trap": actual_trap,
                    "returncode": proc.returncode,
                    "stdout": proc.stdout.strip(),
                    "stderr": proc.stderr.strip(),
                }
            runner = "chronus-reference-emulator-v1"
            runner_sha = cli_sha

        actual = canonical(actual_record)
        actual_sha = _store_bytes(root, "actual", actual, ".json")
        trace_sha = _store_bytes(root, "traces", actual, ".json")
        passed = actual_status == case["expected_status"] and actual_trap == case["expected_trap"]
        _write_result(
            root,
            {
                "schema": "chronus.conformance.result.v1",
                "case_id": case["case_id"],
                "runner": runner,
                "runner_sha256": runner_sha,
                "actual_sha256": actual_sha,
                "trace_sha256": trace_sha,
                "actual_status": actual_status,
                "actual_trap": actual_trap,
                "passed": passed,
            },
        )
        if not passed:
            raise AssertionError(
                f"{case['case_id']} mismatch: expected {case['expected_status']}/{case['expected_trap']}, got {actual_status}/{actual_trap}"
            )
        counts[actual_status] = counts.get(actual_status, 0) + 1

    return counts


def replay_all(root: Path) -> dict:
    root = Path(root)
    semantic = replay_semantic(root)
    machine = replay_machine(root)
    results = [json.loads(path.read_text()) for path in sorted((root / "results" / "reference").glob("*.json"))]
    if not results or not all(result["passed"] for result in results):
        raise AssertionError("reference replay contains non-passing results")
    if any(result["actual_status"] == "NOT_RUN" for result in results):
        raise AssertionError("reference replay left NOT_RUN results")
    return {
        "semantic": semantic,
        "machine": machine,
        "result_count": len(results),
        "results_root": tree_digest(root / "results"),
    }

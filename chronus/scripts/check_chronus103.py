"""Acceptance gate for the typed Chronus subset compiler."""

from __future__ import annotations
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np
from compiler import compile_ir
from format.chronus1_executable import unpack
from tools.asm import assemble_source
from tools.disasm import disassemble


def execute(comp, uploads, dump):
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        exe = td / "x.chronus"
        exe.write_bytes(comp.container)
        cmd = [
            str(ROOT / "chronus/emulator/build/chronus-emu"),
            "--load",
            str(exe),
            "--global",
            ",".join(map(str, comp.geometry.global_size)),
            "--local",
            ",".join(map(str, comp.geometry.local_size)),
            "--memory",
            str(comp.memory["required_bytes"]),
            "--dump",
            f"{dump[0]}:{dump[1]}",
        ]
        for idx, (address, array) in enumerate(uploads):
            p = td / f"in{idx}.bin"
            p.write_bytes(np.asarray(array, dtype=np.float32).tobytes())
            cmd += ["--upload", f"{p}@{address}"]
        return json.loads(subprocess.check_output(cmd, text=True))


def floats(words):
    return np.asarray(words, dtype=np.uint32).view(np.float32)


def load_case(name):
    return json.loads((ROOT / "chronus/compiler/cases" / name).read_text())


def main():
    subprocess.run([sys.executable, "chronus/scripts/check_chronus102.py"], cwd=ROOT, check=True)
    results = {}
    # Type/shape/op fail-closed checks.
    for bad in [
        {"schema": "bad", "name": "x", "op": "vector_add", "dtype": "f32", "shape": {"n": 4}},
        {
            "schema": "chronus.ir.v0.1",
            "name": "x",
            "op": "softmax",
            "dtype": "f32",
            "shape": {"n": 4},
        },
        {
            "schema": "chronus.ir.v0.1",
            "name": "x",
            "op": "vector_add",
            "dtype": "f64",
            "shape": {"n": 4},
        },
        {
            "schema": "chronus.ir.v0.1",
            "name": "x",
            "op": "matmul_tiled",
            "dtype": "f32",
            "shape": {"m": 31, "k": 32, "n": 32},
        },
    ]:
        try:
            compile_ir(bad)
            raise AssertionError("invalid IR compiled")
        except ValueError:
            pass
    print("typed IR rejection                                      PASS")
    # Vector add.
    cv = compile_ir(load_case("vector_add.json"))
    n = cv.ir.shape["n"]
    rng = np.random.default_rng(11)
    a = rng.normal(size=n).astype(np.float32)
    b = rng.normal(size=n).astype(np.float32)
    rv = execute(
        cv,
        [
            (cv.memory["A"], a),
            (cv.memory["B"], b),
            (cv.memory["ONE"], np.asarray([1.0], np.float32)),
        ],
        (cv.memory["C"], n),
    )
    got = floats(rv["dump"])
    err = float(np.max(np.abs(got - (a + b))))
    assert err == 0.0
    results["vector_add"] = {"max_abs_error": err, "trace_hash": rv["trace_hash"]}
    print("compiler vector add semantic verification               PASS")
    # Local reduction.
    cr = compile_ir(load_case("reduce_sum_local.json"))
    n = cr.ir.shape["n"]
    x = rng.normal(size=n).astype(np.float32)
    rr = execute(
        cr,
        [(cr.memory["A"], x), (cr.memory["ONE"], np.asarray([1.0], np.float32))],
        (cr.memory["OUT"], 1),
    )
    got = float(floats(rr["dump"])[0])
    ref = np.float32(0)
    one = np.float32(1)
    for value in x:
        ref = np.float32(np.float32(value) * one + ref)
    err = abs(got - float(ref))
    assert err == 0.0
    results["reduce_sum_local"] = {"max_abs_error": err, "trace_hash": rr["trace_hash"]}
    print("compiler local reduction semantic verification          PASS")
    # Tiled matmul.
    cm = compile_ir(load_case("matmul_tiled.json"))
    a = rng.normal(size=(32, 32)).astype(np.float32)
    b = rng.normal(size=(32, 32)).astype(np.float32)
    rm = execute(cm, [(cm.memory["A"], a), (cm.memory["B"], b)], (cm.memory["C"], 1024))
    got = floats(rm["dump"]).reshape(32, 32)
    ref = a @ b
    err = float(np.max(np.abs(got - ref)))
    assert err <= 1e-5
    results["matmul_tiled"] = {"max_abs_error": err, "trace_hash": rm["trace_hash"]}
    print("compiler tiled matmul semantic verification             PASS")
    # Deterministic compilation and toolchain closure.
    for case in ("vector_add.json", "reduce_sum_local.json", "matmul_tiled.json"):
        ir = load_case(case)
        builds = [compile_ir(ir) for _ in range(10)]
        assert len({hashlib.sha256(c.container).digest() for c in builds}) == 1
        c = builds[0]
        assert assemble_source(disassemble(c.container)) == c.container
        assert unpack(c.container).required_global_bytes == c.memory["required_bytes"]
    print("compiler deterministic + asm/disasm/container closure   PASS")
    evidence = {
        "schema": "chronus103-closure-v1",
        "compiler": "chronus-subset-v0.1",
        "supported_ops": sorted(results),
        "results": results,
        "inherited_gate": "chronus102",
        "status": "PASS",
    }
    raw = json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(raw).hexdigest()
    out = ROOT / "artifacts"
    out.mkdir(exist_ok=True)
    (out / "chronus103-closure.json").write_bytes(raw)
    (out / "chronus103-sha256sums.txt").write_text(f"{digest}  chronus103-closure.json\n")
    print("Chronus-1 PR #103 subset compiler acceptance: PASS")


if __name__ == "__main__":
    main()

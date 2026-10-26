"""Certified portable integer-IR workload, backed by the canonical compiler."""

import hashlib
import struct
from chronus.compiler.exact_kernel import ExactKernelIR


def execute_kernel(value):
    if set(value) != {"ir", "indices", "seed"}:
        raise ValueError("exact_kernel requires ir, indices and seed")
    ir = ExactKernelIR.from_dict(value["ir"])
    rows = ir.execute(value["indices"], value["seed"])
    digest = hashlib.sha256(b"".join(struct.pack("<I", v) for row in rows for v in row)).hexdigest()
    return {"rows": rows, "digest": digest, "legality": ir.legality(), "arithmetic": "exact_uint32"}


def verify_kernel(value, output):
    ir = ExactKernelIR.from_dict(value["ir"])
    expected = ir.reference(value["indices"], value["seed"])
    digest = hashlib.sha256(
        b"".join(struct.pack("<I", v) for row in expected for v in row)
    ).hexdigest()
    return (
        []
        if output
        == {
            "rows": expected,
            "digest": digest,
            "legality": ir.legality(),
            "arithmetic": "exact_uint32",
        }
        else ["portable exact IR invariant mismatch"]
    )

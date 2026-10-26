"""Compile and execute bounded Chronus RTL conformance in a temporary directory.

Requires GHDL on PATH. Testbench execution verifies VHDL semantics; this command
makes no FPGA synthesis, silicon clock-rate or physical acceleration claim.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
import random
import subprocess
import tempfile

from kellogg.scales import Zphi

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    sources = [ROOT / "hyba.vhd"] + [
        ROOT / "chronus/hardware" / name
        for name in ("golden_stride.vhd", "tb_exact_datapath.vhd", "tb_golden_stride.vhd")
    ]
    with tempfile.TemporaryDirectory(prefix="chronus-rtl-") as directory:
        work = Path(directory)
        vector_file = work / "phi_vectors.txt"
        edges = (-32768, -1, 0, 1, 32767)
        vectors = list(itertools.product(edges, repeat=4))
        for seed in (1337, 42, 2026):
            rng = random.Random(seed)
            vectors.extend(tuple(rng.randrange(-32768, 32768) for _ in range(4)) for _ in range(64))
        lines = []
        for a, b, c, d in vectors:
            expected = Zphi(a, b) * Zphi(c, d)
            lines.append(
                f"{a} {b} {c} {d} {expected.a & ((1 << 64)-1):016x} {expected.b & ((1 << 64)-1):016x}"
            )
        vector_file.write_text("\n".join(lines) + "\n", encoding="ascii")
        subprocess.run(["ghdl", "-a", "--std=08", *(str(s) for s in sources)], cwd=work, check=True)
        for entity in ("hyba", "chronus_golden_stride"):
            with (work / f"{entity}.netlist.vhd").open("w") as netlist:
                subprocess.run(
                    ["ghdl", "--synth", "--std=08", entity],
                    cwd=work,
                    stdout=netlist,
                    check=True,
                    timeout=60,
                )
        for bench in ("tb_exact_datapath", "tb_golden_stride"):
            subprocess.run(["ghdl", "-e", "--std=08", bench], cwd=work, check=True)
            command = ["ghdl", "-r", "--std=08", bench]
            if bench == "tb_exact_datapath":
                command.append(f"-gvectors_path={vector_file}")
            subprocess.run(command + ["--assert-level=error"], cwd=work, check=True, timeout=60)
    print(
        json.dumps(
            {
                "status": "passed",
                "kind": "rtl_conformance",
                "synthesis_elaboration": True,
                "phi_vectors": len(vectors),
                "gf256_products": 65536,
                "physical_device_execution": False,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""One-command acceptance gate for Chronus executable/ABI/emulator closure."""

from __future__ import annotations
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from format.chronus1_executable import Executable, Symbol, load, pack, unpack, write
from chronus.emulator.evidence import canonical, execute


# Canonical instruction helpers used only to create the byte-level fixture.
def i(op, rd, rs, imm):
    return (op << 26) | ((rd & 31) << 21) | ((rs & 31) << 16) | (imm & 0xFFFF)


def r(op, rd=0, a=0, b=0, aux=0):
    return (op << 26) | (rd << 21) | (a << 16) | (b << 11) | (aux << 6)


def run(command, **kw):
    print("+", *map(str, command))
    return subprocess.run(command, cwd=ROOT, check=True, **kw)


def expect_cli_trap(cli, path):
    p = subprocess.run([str(cli), "--load", str(path)], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 2, (p.returncode, p.stdout, p.stderr)


def main():
    run([sys.executable, "chronus/scripts/check_chronus_isa.py"])
    run([sys.executable, "chronus/scripts/check_chronus_emulator.py"])
    cli = ROOT / "chronus/emulator/build/chronus-emu"
    assert cli.is_file()
    code = (i(2, 1, 0, 2), i(2, 2, 0, 2), r(3, 3, 1, 2), i(9, 3, 0, 0), r(63))
    exe = Executable(
        code,
        required_global_bytes=1024,
        symbols=(Symbol("main", 0, len(code) * 4, 1, 0),),
        reconvergence=(),
    )
    blob = pack(exe)
    parsed = unpack(blob)
    assert parsed == exe and pack(parsed) == blob
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        good = td / "2plus2.chronus"
        write(good, exe)
        assert load(good) == exe
        bad = bytearray(blob)
        bad[-1] ^= 1
        (td / "bad-crc.chronus").write_bytes(bad)
        expect_cli_trap(cli, td / "bad-crc.chronus")
        bad = bytearray(blob)
        bad[4] = 2
        (td / "bad-version.chronus").write_bytes(bad)
        expect_cli_trap(cli, td / "bad-version.chronus")
        outputs = []
        digests = []
        for _ in range(100):
            record, d = execute(cli, good, memory=1024, dump=(0, 1))
            outputs.append(record["validation"]["output_hash"])
            digests.append(d)
        assert len(set(outputs)) == len(set(digests)) == 1
        assert json.loads(
            subprocess.check_output(
                [str(cli), "--load", str(good), "--memory", "1024", "--dump", "0:1"], text=True
            )
        )["dump"] == [4]
        artifact = canonical(record)
        assert hashlib.sha256(artifact).hexdigest() == digests[0]
        out = ROOT / "artifacts"
        out.mkdir(exist_ok=True)
        (out / "chronus101-evidence.json").write_bytes(artifact)
        (out / "chronus101-sha256sums.txt").write_text(f"{digests[0]}  chronus101-evidence.json\n")
    source = "\n".join(
        p.read_text(errors="ignore") for p in (ROOT / "chronus/emulator").rglob("*.cpp")
    )
    assert "case Opcode::NOP" in source and "default:" in source and "IllegalOpcode" in source
    assert not any(
        x in source.lower() for x in ("fallback_to_host", "execute_on_host", "silent_nop")
    )
    print(
        "Chronus #101 closure gate: PASS (format, ABI, 1M decode fuzz, 100x replay, evidence hash)"
    )


if __name__ == "__main__":
    main()

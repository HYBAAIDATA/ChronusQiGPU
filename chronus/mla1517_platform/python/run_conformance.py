import json
import pathlib
import subprocess

root = pathlib.Path(__file__).resolve().parents[1]
bin_path = root / "results" / "mla1517_cpu"
subprocess.run(
    [
        "g++",
        "-std=c++17",
        "-O2",
        "-I",
        str(root / "contracts"),
        str(root / "cpp/src/mla1517_cpu.cpp"),
        "-o",
        str(bin_path),
    ],
    check=True,
)
raw = subprocess.check_output([str(bin_path)], text=True).strip()
cpp = json.loads(raw)
assert cpp == {
    "cassini": True,
    "lucas": True,
    "zeckendorf": True,
    "fibonacci_15": 610,
    "lucas_15": 1364,
}, cpp
(root / "results" / "cpp_conformance.json").write_text(json.dumps(cpp, indent=2) + "\n")
print(json.dumps({"status": "PASS", "cpp_conformance": cpp}, indent=2))

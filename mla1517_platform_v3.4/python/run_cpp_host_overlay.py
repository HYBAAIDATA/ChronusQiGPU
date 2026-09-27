import json
import pathlib
import subprocess

root = pathlib.Path(__file__).resolve().parents[1]
out = root / "results" / "mla1517_host_overlay"
subprocess.run(
    [
        "g++",
        "-std=c++17",
        "-O3",
        "-pthread",
        "-I",
        str(root / "cpp/include"),
        str(root / "cpp/src/mla1517_host_overlay.cpp"),
        "-o",
        str(out),
    ],
    check=True,
)
data = json.loads(subprocess.check_output([str(out)], text=True))
assert data["status"] == "PASS" and data["coverage"] and data["kernel"]
(root / "results" / "cpp_host_overlay.json").write_text(json.dumps(data, indent=2) + "\n")
print(json.dumps(data, indent=2))

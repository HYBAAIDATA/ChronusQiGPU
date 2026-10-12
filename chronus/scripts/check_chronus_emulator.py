"""Build and run the fail-closed Chronus-1 emulator acceptance gate."""

from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def run(cmd):
    print("+", *map(str, cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main():
    build = ROOT / "chronus/emulator/build"
    build.mkdir(parents=True, exist_ok=True)
    cmake = shutil.which("cmake")
    if cmake:
        run([cmake, "-S", "chronus/emulator", "-B", str(build), "-DCMAKE_BUILD_TYPE=Release"])
        run([cmake, "--build", str(build), "--config", "Release", "--parallel"])
        run(["ctest", "--test-dir", str(build), "--output-on-failure", "-C", "Release"])
    else:
        cxx = shutil.which("g++") or shutil.which("clang++")
        assert cxx, "C++17 compiler unavailable"
        common = [
            cxx,
            "-std=c++17",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-ffp-contract=off",
            "-Ichronus/emulator/include",
        ]
        core = [
            "chronus/emulator/src/decode.cpp",
            "chronus/emulator/src/memory.cpp",
            "chronus/emulator/src/loader.cpp",
            "chronus/emulator/src/emulator.cpp",
        ]
        run(
            common
            + core
            + [
                "chronus/emulator/tests/test_emulator.cpp",
                "-o",
                str(build / "chronus-emulator-tests"),
            ]
        )
        run([str(build / "chronus-emulator-tests")])
        run(common + core + ["chronus/emulator/src/main.cpp", "-o", str(build / "chronus-emu")])
    sources = "\n".join(
        p.read_text(errors="ignore") for p in (ROOT / "chronus/emulator").rglob("*.cpp")
    )
    assert "default:" in sources and "IllegalOpcode" in sources
    assert not any(
        x in sources.lower() for x in ("fallback_to_host", "execute_on_host", "silent_nop")
    )
    print("Chronus-1 emulator evidence gate: PASS")


if __name__ == "__main__":
    main()

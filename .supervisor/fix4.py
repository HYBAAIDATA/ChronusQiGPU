#!/usr/bin/env python3
"""Run 4 fixes on chore/turing-packaging-consolidation-20261111 (found by run 3)."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
SUP = Path(sys.argv[1])

FRAGMENTS_README = """# Source fragments held out of the shipped package

These files are kept exactly as committed. Nothing imports them and Python cannot compile them, so they are held here instead of inside the `hyba-chronus` distribution, whose checks now require every shipped module to compile.

| File | Former path | Added in | Why it is held here |
|---|---|---|---|
| trust_ledger.py | src/chronus/core/trust_ledger.py | e04dbd0 (9 Nov 2026) | Line 1 is an escaped docstring (a backslash before each quote), which Python rejects. The file also uses `dataclass`, `field`, `Dict`, `datetime` and a `Touchpoint` type that it never imports or defines. |

To restore a file, complete it so that it compiles and has tests, then move it back to its former path in the same change.
"""

README_SPEC = """
## Specification

The build contract for the canonical algorithm suite (Deutsch–Jozsa, Bernstein–Vazirani, Simon, Grover, the quantum Fourier transform, quantum phase estimation and Shor's order finding) is [docs/SPECIFICATION.md](docs/SPECIFICATION.md).
"""

LAYOUT_TESTS = '''

def test_every_module_in_the_distributions_compiles():
    failures = []
    for base in (ROOT / "src" / "chronus", ROOT / "packages" / "turing" / "src" / "turing"):
        for path in sorted(base.rglob("*.py")):
            try:
                compile(path.read_bytes(), str(path), "exec", dont_inherit=True)
            except SyntaxError as error:
                failures.append(f"{path.relative_to(ROOT)}:{error.lineno}: {error.msg}")
    assert failures == []


def test_distributions_ship_disjoint_packages():
    tomllib = pytest.importorskip("tomllib")
    root = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    turing = tomllib.loads((ROOT / "packages" / "turing" / "pyproject.toml").read_text(encoding="utf-8"))
    root_find = root["tool"]["setuptools"]["packages"]["find"]
    turing_find = turing["tool"]["setuptools"]["packages"]["find"]
    assert root_find["where"] == ["src"]
    assert not any(pattern.startswith("turing") for pattern in root_find["include"])
    assert all(pattern.startswith("turing") for pattern in turing_find["include"])
'''


def log(message):
    print(message, flush=True)


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def edit(relative, old, new):
    path = ROOT / relative
    data = path.read_bytes().decode("utf-8")
    if "\r\n" in data:
        old, new = old.replace("\n", "\r\n"), new.replace("\n", "\r\n")
    found = data.count(old)
    if found != 1:
        raise SystemExit(f"edit failed: {relative}: expected 1 occurrence, found {found}: {old!r}")
    path.write_bytes(data.replace(old, new).encode("utf-8"))
    log(f"edited: {relative}")


def main():
    # 1. Non-compiling, unimported fragment leaves the shipped package unchanged.
    fragment = "src/chronus/core/trust_ledger.py"
    target = "archive/fragments/trust_ledger.py"
    (ROOT / "archive" / "fragments").mkdir(parents=True, exist_ok=True)
    run("git", "mv", fragment, target)
    log(f"moved: {fragment} -> {target}")
    (ROOT / "archive" / "fragments" / "README.md").write_text(FRAGMENTS_README, encoding="utf-8")
    log("wrote: archive/fragments/README.md")
    policy_path = ROOT / "scripts/ci/claim_token_policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    before = len(policy["allowlist"])
    policy["allowlist"] = [e for e in policy["allowlist"] if e["path"] != fragment]
    if len(policy["allowlist"]) != before:
        policy_path.write_text(json.dumps(policy, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        log("claim allowlist: removed the trust_ledger entry (archive/ is excluded)")

    # 2. hyba-chronus ships Chronus only; TURING ships only as hyba-turing.
    edit("pyproject.toml",
         'where = ["src", "packages/turing/src"]\ninclude = ["chronus*", "turing*"]',
         'where = ["src"]\ninclude = ["chronus*"]')
    edit("pyproject.toml",
         'description = "Chronus: the HYBA Data exact-computation platform, bundled with the TURING library (internal distribution)"',
         'description = "Chronus: the HYBA Data exact-computation platform (internal distribution; TURING ships separately as hyba-turing)"')

    # 3. The API image does not import TURING, so it no longer copies it.
    edit("Dockerfile", "COPY packages/turing/src ./packages/turing/src\n", "")

    # 4. Unused imports reported by ruff on the new paths.
    edit("src/chronus/igpu/tensor.py",
         "from chronus.tensor.enhanced_representation import EnhancedTensorRepresentation\n",
         "from chronus.tensor.enhanced_representation import (\n"
         "    EnhancedTensorRepresentation as EnhancedTensorRepresentation,\n)\n")
    edit("packages/turing/src/turing/operator.py",
         "import math\nfrom dataclasses import dataclass",
         "from dataclasses import dataclass")

    # 5. Specification, README pointer, wheel check and layout tests.
    docs = ROOT / "packages" / "turing" / "docs"
    docs.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUP / "SPECIFICATION.md", docs / "SPECIFICATION.md")
    log("wrote: packages/turing/docs/SPECIFICATION.md")
    readme = ROOT / "packages" / "turing" / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8").rstrip("\n") + "\n" + README_SPEC, encoding="utf-8")
    log("appended: packages/turing/README.md")
    shutil.copyfile(SUP / "check_wheels.py", ROOT / "scripts" / "ci" / "check_wheels.py")
    log("wrote: scripts/ci/check_wheels.py")
    edit("tests/test_repository_layout.py",
         "import re\nfrom pathlib import Path\n",
         "import re\nfrom pathlib import Path\n\nimport pytest\n")
    layout = ROOT / "tests" / "test_repository_layout.py"
    layout.write_text(layout.read_text(encoding="utf-8").rstrip("\n") + "\n" + LAYOUT_TESTS, encoding="utf-8")
    log("appended: tests/test_repository_layout.py")

    run("git", "add", "-A")
    log(run("git", "status", "--short"))


if __name__ == "__main__":
    main()

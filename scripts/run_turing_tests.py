"""Run against the canonical package, before pytest loads umbrella namespaces.

Usage: python path/to/run_tests.py /path/to/EuclidPhiEnterprise-main [pytest args]
Requires pytest. Default: added API suite. --all: native TURING package suite.
"""

import os
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
package_root = root / "turing_universal_quantum_computer"
sys.path[:0] = [str(package_root), str(root)]
import turing_universal_quantum_computer as turing

if (
    Path(turing.__file__).resolve()
    != package_root / "turing_universal_quantum_computer" / "__init__.py"
):
    raise SystemExit("Refusing: imported the wrong TURING package")
import pytest

os.chdir(root)
args = sys.argv[2:]
full = "--all" in args
args = [a for a in args if a != "--all"]
target = (
    "turing_universal_quantum_computer/tests"
    if full
    else "turing_universal_quantum_computer/tests/test_public_api_dropin.py"
)
raise SystemExit(pytest.main(["--confcutdir=" + str(package_root), target, "-q", *args]))

#!/usr/bin/env python3
"""AL HARAS (HYBA Security) engine self-test: command-line demonstration.

The original prototype described an operating-system kernel. What exists is a
user-space library; this script runs its exact self-tests and one process
admission, using src/chronus/security/al_haras/topological_os.py. It no longer
loads chronus_gpiu-v36.py. See docs/security/AL_HARAS_NOTES_RECONCILIATION.md.
"""

import json
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src"
if SRC not in sys.path:
    sys.path.insert(0, str(SRC))

from chronus.security.al_haras.topological_os import (  # noqa: E402
    ALHarasSovereignOSProduct,
    ALHarasTopologicalKernel,
)

__all__ = ["ALHarasSovereignOSProduct", "ALHarasTopologicalKernel"]


def main() -> int:
    kernel = ALHarasTopologicalKernel("demo_tenant")
    boot = kernel.boot_kernel()
    process = kernel.execute_sovereign_process("demo_process", b"EXAMPLE", state_vectors=[[1, 0], [1, 0]])
    print(json.dumps({"self_test": boot, "process_admitted": process["process_admitted"]}, indent=2))
    return 0 if boot["boot_status"] == "SELF_TEST_PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())

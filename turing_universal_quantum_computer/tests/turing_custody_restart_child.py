"""Fresh-process custody re-attach + replay for test_vqc_custody_durable.py.

Runs the real adapter path — ``open_custody(durable_dir=...)`` →
``Theseus.attach`` → digest-verified heal — with no live objects shared with
the parent process.  Mirrors tests/euclid_custody_restart_child.py: nonzero
exit and the failure body on stdout when the boundary does not verify.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: turing_custody_restart_child.py <custody_dir> <uid>")
        return 2
    try:
        from turing_universal_quantum_computer.custody import open_custody
    except Exception as exc:  # pragma: no cover - exercised by parent test
        print(f"custody unavailable in child process: {exc}")
        return 3

    custody = open_custody(durable_dir=sys.argv[1])
    report = custody.replay(sys.argv[2])
    print(json.dumps(report.as_dict()))
    return 0 if report.state == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())

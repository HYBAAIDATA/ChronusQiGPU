"""Run the full adversarial evaluation suite and emit JSON artifacts.

Usage: python -m eval_harness.run_all
Writes eval_harness/artifacts/*.json and prints a compact summary.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from environment import write_artifact  # noqa: E402

import falsification  # noqa: E402
import heldout_eval  # noqa: E402
import memory_influence  # noqa: E402
import reachability_audit  # noqa: E402
import reward_audit  # noqa: E402


def main():
    started = time.time()
    artifacts = {}

    falsification_results = falsification.run_all()
    artifacts["falsification"] = write_artifact("falsification", falsification_results)
    artifacts["reward_audit"] = write_artifact("reward_audit", reward_audit.run_all())
    artifacts["memory_influence"] = write_artifact("memory_influence", memory_influence.run_all())
    artifacts["heldout_eval"] = write_artifact("heldout_eval", heldout_eval.run_all())
    artifacts["capability_matrix"] = write_artifact(
        "capability_matrix", reachability_audit.run_all()
    )

    summary = {
        "schema": "euclid.adversarial.review/1",
        "elapsed_s": round(time.time() - started, 2),
        "artifacts": {k: str(v) for k, v in artifacts.items()},
        "falsification_verdicts": {
            name: result.get("verdict") for name, result in falsification_results.items()
        },
    }
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return summary


if __name__ == "__main__":
    main()

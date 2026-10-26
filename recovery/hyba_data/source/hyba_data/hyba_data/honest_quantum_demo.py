"""Honest quantum demo — HYBA Data (quantum ubiquitous; mining not a product surface).

Run:
  PYTHONPATH=python_backend python3 -m hyba_data.honest_quantum_demo
"""

from __future__ import annotations

import json
from pathlib import Path

from hyba_data.quantum_honest import help_hyba_data, run_honest_quantum_battery, step_demo


def build_demo_report() -> dict:
    battery = run_honest_quantum_battery()
    help_ = help_hyba_data()
    demo = step_demo(n_items=256, shots=128)
    return {
        "company": "HYBA Data",
        "title": "Honest Quantum Demo",
        "status": battery["status"],
        "quantum_is_mathematics": True,
        "ubiquitous": True,
        "mining": False,
        "battery": battery,
        "help": {"catalog": help_["catalog"], "status": help_["status"]},
        "demo": demo,
        "repo_path": "python_backend/hyba_data/honest_quantum_demo.py",
        "module": "hyba_data.quantum_honest",
    }


def main() -> int:
    report = build_demo_report()
    art = Path("artifacts/hyba_data")
    art.mkdir(parents=True, exist_ok=True)
    out = art / "HONEST_QUANTUM_DEMO_REPORT.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "wrote": str(out),
                "status": report["status"],
                "mining": False,
                "ubiquitous": True,
            },
            indent=2,
        )
    )
    return 0 if report["status"] == "HONEST_QUANTUM_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

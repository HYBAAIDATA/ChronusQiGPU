#!/usr/bin/env python3
"""Execute every isolated L-HRAS blueprint module and functional check."""
from __future__ import annotations
import importlib
import json
import pkgutil
import time
from pathlib import Path

PACKAGE = "l_hras.experimental.blueprint"


def main() -> int:
    package = importlib.import_module(PACKAGE)
    modules = sorted(m.name for m in pkgutil.walk_packages(package.__path__, PACKAGE + "."))
    results = {"modules": {}, "functional_tests": {}}
    for name in modules:
        if ".blueprint_tests." in name:
            continue
        try:
            module = importlib.import_module(name)
            runner = getattr(module, "run_invariants", None)
            if callable(runner):
                runner()
            results["modules"][name] = {"status": "pass"}
        except Exception as exc:
            results["modules"][name] = {"status": "fail", "error": f"{type(exc).__name__}: {exc}"}
    for module_name in (
        PACKAGE + ".blueprint_tests.test_all",
        PACKAGE + ".blueprint_tests.test_asic_blueprint",
    ):
        module = importlib.import_module(module_name)
        for name in sorted(n for n in vars(module) if n.startswith("test_")):
            started = time.perf_counter()
            try:
                getattr(module, name)()
                row = {"status": "pass"}
            except Exception as exc:
                row = {"status": "fail", "error": f"{type(exc).__name__}: {exc}"}
            row["elapsed_ms"] = (time.perf_counter() - started) * 1000
            results["functional_tests"][f"{module_name}::{name}"] = row
    results["summary"] = {
        "module_pass": sum(v["status"] == "pass" for v in results["modules"].values()),
        "module_fail": sum(v["status"] == "fail" for v in results["modules"].values()),
        "test_pass": sum(v["status"] == "pass" for v in results["functional_tests"].values()),
        "test_fail": sum(v["status"] == "fail" for v in results["functional_tests"].values()),
    }
    print(json.dumps(results, indent=2, sort_keys=True))
    return int(results["summary"]["module_fail"] > 0 or results["summary"]["test_fail"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())

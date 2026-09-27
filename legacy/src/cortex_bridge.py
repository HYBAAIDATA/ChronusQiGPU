#!/usr/bin/env python3
"""
EUCLID-CORE Cortex Bridge — JSON CLI adapter.

Exposes the dropped-in HYBA cortex modules and the UniversalPredictor to the
TypeScript backend. Each invocation is a single call:

    python src/cortex_bridge.py <command> '<json payload>'

Commands:
    status                Module availability (no heavy work)
    assess                Full cortex assessment of a numeric context vector
    predict               UniversalPredictor risk profile for entity data

Output: one JSON object on stdout. Errors are reported as
{"success": false, "error": "..."} with exit code 1.
"""

import json
import os
import sys

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_ENGINE = os.path.join(SRC_DIR, "..", "core_engine")
sys.path.insert(0, SRC_DIR)
sys.path.insert(0, os.path.abspath(CORE_ENGINE))


def _jsonable(obj):
    import numpy as np

    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def cmd_status():
    import numpy  # noqa: F401 — required dependency check

    modules = {}
    for name in (
        "cortex_golden_transform",
        "cortex_topological_context",
        "cortex_spectral_context",
        "cortex_gauge_training",
    ):
        try:
            __import__(name)
            modules[name] = True
        except Exception:
            modules[name] = False
    try:
        from universal_predictor.universal_predictor import UniversalPredictor  # noqa: F401

        modules["universal_predictor"] = True
    except Exception:
        modules["universal_predictor"] = False
    return {"success": True, "modules": modules}


def cmd_assess(payload):
    import numpy as np
    from cortex_golden_transform import CortexGoldenTransformFolding
    from cortex_topological_context import CortexTopologicalContext
    from cortex_spectral_context import CortexSpectralContext

    vector = np.asarray(payload.get("context", []), dtype=float)
    if vector.size == 0:
        vector = np.linspace(0.0, 1.0, 32)
    epoch = int(payload.get("epoch", 0))

    golden = CortexGoldenTransformFolding()
    topo = CortexTopologicalContext()
    spectral = CortexSpectralContext()

    metrics = golden.get_training_metrics(epoch, vector)
    signature = topo.get_context_signature(vector)
    spectral_stats = spectral.get_spectral_stats()

    return {
        "success": True,
        "golden": metrics,
        "topological": signature,
        "spectral": spectral_stats,
    }


def cmd_predict(payload):
    from universal_predictor.universal_predictor import UniversalPredictor

    entity_data = payload.get("entity_data", {})
    predictor = UniversalPredictor()
    return {"success": True, "profile": predictor.predict_risk(entity_data)}


def main():
    if len(sys.argv) < 2:
        print(
            json.dumps({"success": False, "error": "usage: cortex_bridge.py <command> [payload]"})
        )
        sys.exit(2)
    command = sys.argv[1]
    payload = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

    handlers = {
        "status": lambda: cmd_status(),
        "assess": lambda: cmd_assess(payload),
        "predict": lambda: cmd_predict(payload),
    }
    if command not in handlers:
        print(json.dumps({"success": False, "error": f"unknown command: {command}"}))
        sys.exit(2)
    try:
        print(json.dumps(_jsonable(handlers[command]())))
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Create SHA-256-pinned Chronus input files from actual scikit-learn UCI datasets.

No synthetic data or downloads. Never promotes public datasets to customer or
production qualification. scikit-learn is optional: install it for this tool.
"""
from __future__ import annotations

import argparse
import hashlib
from importlib.resources import files
import io
import json
from pathlib import Path
import platform
import shutil
import sys
import tempfile

import numpy as np
import yaml

SCHEMA = "chronus.real-workload-manifest/1"
SOURCE_CLASS = "PUBLIC_OBSERVED_DATASET"
# These SHA-256 anchors were independently computed for scikit-learn 1.8.0.
PINNED = {
    "uci_digits.npy": "0f1c225bbabf3d4eaccd81f73c9594ceec77d84c9b425ef0e4cc815743050529",
    "uci_wine.npy": "09af9db3ce2a52b3f168d5d9eb1d4d4ceba584fad9e0e9aba63ff536c192c6a6",
    "uci_breast_cancer.npy": "602e781b91843b0ea3dc8bf3ff3e63055985230cad47c45a5099780e3c33459f",
    "uci_wine_packaged_file.snapshot": "10e8a802908b34f86e5da8ce962f3c806694bc98450a18f61851af59f324bede",
}
SETS = (
    ("digits", "1797x64", "https://archive.ics.uci.edu/dataset/80/optical+recognition+of+handwritten+digits"),
    ("wine", "178x13", "https://archive.ics.uci.edu/dataset/109/wine"),
    ("breast_cancer", "569x30", "https://archive.ics.uci.edu/dataset/17/breast+cancer+wisconsin+diagnostic"),
)


def prepare(output: Path) -> dict:
    import sklearn
    from sklearn.datasets import load_digits, load_wine, load_breast_cancer

    # A pinned input policy: a changed upstream package must be reviewed,
    # not silently used with historical measurement SHA-256 anchors.
    if sklearn.__version__ != "1.8.0":
        raise ValueError("requires scikit-learn 1.8.0 to reproduce pinned inputs")
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise ValueError("destination must not already exist; never overwrite an existing source")
    loaders = {"digits": load_digits, "wine": load_wine,
               "breast_cancer": load_breast_cancer}
    planned = []
    sources = []
    for name, shape, url in SETS:
        array = np.ascontiguousarray(loaders[name]().data, dtype=np.float64)
        rows, cols = (int(part) for part in shape.split("x"))
        if array.shape != (rows, cols) or not np.all(np.isfinite(array)):
            raise ValueError(f"{name} observed dataset no longer matches declared shape")
        memory = io.BytesIO()
        np.save(memory, array, allow_pickle=False)
        payload = memory.getvalue()
        filename = f"uci_{name}.npy"
        if hashlib.sha256(payload).hexdigest() != PINNED[filename]:
            raise ValueError(f"pinned input SHA-256 mismatch: {filename}")
        planned.append((filename, payload))
        sources.append({
            "path": filename, "kind": "tensor",
            "sha256": PINNED[filename], "source_class": SOURCE_CLASS,
            "provenance": f"UCI observed dataset via scikit-learn 1.8.0, source {url}; original features unaltered",
        })
    # Copies packaged UCI source bytes. This is an opaque byte-preservation
    # workload, NOT an actual Chronus runtime state/checkpoint.
    raw = files("sklearn.datasets.data").joinpath("wine_data.csv").read_bytes()
    snapshot = "uci_wine_packaged_file.snapshot"
    if hashlib.sha256(raw).hexdigest() != PINNED[snapshot]:
        raise ValueError("wine source bytes differ from verified scikit-learn 1.8.0")
    planned.append((snapshot, raw))
    sources.append({
        "path": snapshot, "kind": "snapshot", "sha256": PINNED[snapshot],
        "source_class": SOURCE_CLASS,
        "provenance": "Unmodified bundled sklearn.datasets.data/wine_data.csv, original observed source bytes; not a deployed state",
    })
    # Stage all objects first; a failed conversion/write never leaves a
    # misleading or unretryable partially created destination.
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".uci-source-staging-", dir=output.parent))
    try:
        for filename, payload in planned:
            with (stage / filename).open("xb") as stream:
                stream.write(payload)
        manifest = {"schema": SCHEMA, "data_sources": sources}
        with (stage / "manifest.yaml").open("x", encoding="utf-8") as stream:
            yaml.safe_dump(manifest, stream, sort_keys=False)
        report = {"schema": "chronus.public-uci-provenance/1",
                  "classification": SOURCE_CLASS,
                  "input_data_generated": False,
                  "upstream": "UCI observational datasets redistributed in scikit-learn",
                  "scikit_learn": sklearn.__version__,
                  "numpy": np.__version__, "python": platform.python_version(),
                  "datasets": [{"name": filename, "bytes": len(payload),
                                "sha256": PINNED[filename]} for filename, payload in planned]}
        with (stage / "provenance.json").open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2)
        if output.exists():
            raise ValueError("destination appeared while preparing input")
        stage.rename(output)
    finally:
        # No-op after successful rename; cleans partial staging on exceptions.
        shutil.rmtree(stage, ignore_errors=True)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps({"result": "PASS", **prepare(args.output)}, indent=2))
        return 0
    except (OSError, ValueError, ImportError) as exc:
        print(json.dumps({"result": "FAIL", "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

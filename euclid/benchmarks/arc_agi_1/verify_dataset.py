"""Validate vendored ARC data without exposing puzzle contents."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def valid_grid(grid):
    return (isinstance(grid, list) and 1 <= len(grid) <= 30
            and all(isinstance(row, list) and len(row) == len(grid[0]) for row in grid)
            and 1 <= len(grid[0]) <= 30
            and all(type(v) is int and 0 <= v <= 9 for row in grid for v in row))


def verify():
    manifest = json.loads((ROOT / "dataset_manifest.json").read_text())
    seen = set()
    actual = set()
    for split in ("training", "evaluation"):
        paths = sorted((ROOT / "data" / split).glob("*.json"))
        if len(paths) != 400:
            raise ValueError(f"Expected 400 {split} tasks, got {len(paths)}")
        for path in paths:
            if path.stem in seen:
                raise ValueError("Duplicate task ID")
            seen.add(path.stem)
            actual.add(path.relative_to(ROOT).as_posix())
            obj = json.loads(path.read_bytes())
            for key in ("train", "test"):
                if not isinstance(obj.get(key), list) or not obj[key]:
                    raise ValueError(f"Invalid pairs: {path.name}")
                for pair in obj[key]:
                    if not valid_grid(pair["input"]) or not valid_grid(pair["output"]):
                        raise ValueError(f"Invalid grid: {path.name}")
    if actual != {item["path"] for item in manifest["tasks"]}:
        raise ValueError("Manifest file set mismatch")
    for item in manifest["tasks"]:
        if hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Checksum mismatch: {item['path']}")
    print("Verified 800 ARC-AGI-1 tasks: 400 training + 400 evaluation; all checksums valid.")


if __name__ == "__main__":
    verify()

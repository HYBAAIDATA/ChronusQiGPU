"""Content-addressed evidence-pack writer."""
from __future__ import annotations
from pathlib import Path
import hashlib, json

class EvidencePack:
    def __init__(self, root: str | Path): self.root = Path(root)
    def write_json(self, phase: str, name: str, payload: dict) -> Path:
        path = self.root / phase / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return path
    def write_text(self, phase: str, name: str, text: str) -> Path:
        path = self.root / phase / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text); return path
    def seal(self, phase: str) -> Path:
        directory = self.root / phase; rows = []
        for path in sorted(p for p in directory.rglob('*') if p.is_file() and p.name != 'manifest.sha256'):
            rows.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(directory)}")
        manifest = directory / 'manifest.sha256'; manifest.write_text('\n'.join(rows) + '\n'); return manifest

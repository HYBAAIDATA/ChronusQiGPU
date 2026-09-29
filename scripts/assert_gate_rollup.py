import json
from pathlib import Path

results = [
    json.loads(p.read_text())
    for p in Path("results").glob("*.json")
    if "status" in json.loads(p.read_text())
]
failed = [r for r in results if r["status"] in {"FAIL", "ERROR"}]
print(json.dumps({"total": len(results), "failed": [r["gate"] for r in failed]}, indent=2))
raise SystemExit(1 if failed else 0)

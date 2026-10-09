import json
from . import run_triad
report=run_triad();print(json.dumps(report.to_dict(),indent=2));raise SystemExit(0 if report.passed else 1)

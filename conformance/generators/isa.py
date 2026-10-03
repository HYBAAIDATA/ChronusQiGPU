"""ISA-only case declarations. This module never imports compiler lowering."""
import json
from pathlib import Path
def cases():return json.loads((Path(__file__).resolve().parents[1]/'machine_cases.json').read_text())

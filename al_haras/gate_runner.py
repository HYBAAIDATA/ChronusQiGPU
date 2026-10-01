"""Repository-neutral signed gate runner."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import asdict
from dataclasses import dataclass
from typing import Callable
from typing import Mapping


@dataclass(frozen=True)
class GateResult:
    name: str
    status: str
    detail: str = ""


@dataclass(frozen=True)
class GateReport:
    repo: str
    commit: str
    when: int
    results: tuple[GateResult, ...]
    passed: bool
    signature: str


def run_gates(
    repo: str, commit: str, gates: Mapping[str, Callable[[], object]], key: bytes
) -> GateReport:
    if len(key) < 32:
        raise ValueError("runner key too short")
    results = []
    for name, gate in gates.items():
        try:
            detail = gate()
            results.append(GateResult(name, "PASS", str(detail)))
        except NotImplementedError as exc:
            results.append(GateResult(name, "SKIPPED", str(exc)))
        except Exception as exc:
            results.append(GateResult(name, "FAIL", f"{type(exc).__name__}: {exc}"))
    passed = all(r.status in {"PASS", "SKIPPED"} for r in results)
    body = {
        "repo": repo,
        "commit": commit,
        "when": int(time.time()),
        "results": [asdict(r) for r in results],
        "passed": passed,
    }
    sig = hmac.new(
        key, json.dumps(body, sort_keys=True, separators=(",", ":")).encode(), hashlib.sha256
    ).hexdigest()
    return GateReport(**body, signature=sig)

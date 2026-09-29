"""Uniform file-backed gate result library."""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    ERROR = "ERROR"


@dataclass(frozen=True)
class Outcome:
    status: Status
    reason: str
    artifacts: tuple[str, ...] = ()


@dataclass(frozen=True)
class GateResult:
    gate: str
    status: Status
    reason: str
    artifacts: tuple[str, ...]
    started_at: int
    finished_at: int


def run(name: str, fn: Callable[[Path], Outcome], repo_root: Path) -> GateResult:
    start = time.time_ns()
    try:
        outcome = fn(repo_root)
        if not isinstance(outcome, Outcome):
            raise TypeError("gate did not return Outcome")
        result = GateResult(
            name, outcome.status, outcome.reason, outcome.artifacts, start, time.time_ns()
        )
    except Exception as exc:
        result = GateResult(
            name, Status.ERROR, f"{type(exc).__name__}: {exc}", (), start, time.time_ns()
        )
    path = repo_root / "results" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            asdict(result),
            sort_keys=True,
            indent=2,
            default=lambda x: x.value if isinstance(x, Enum) else str(x),
        )
    )
    return result

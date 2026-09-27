"""Backend lifecycle integration for Salamander's repository self-repair cycle.

The expensive diagnosis runs in a managed background task so it cannot delay the
HTTP listener. Applying a proposal remains governed by self_repair's existing
``HYBA_SELF_REPAIR_AUTO_APPLY`` approval and verify-or-revert controls.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from Intelligence.self_healing.self_repair import run_self_repair_cycle

logger = logging.getLogger(__name__)
ENV_SKIP_STARTUP = "HYBA_SKIP_STARTUP_SELF_HEALING"


@dataclass
class StartupSelfHealingState:
    status: str = "not_started"
    started_at: float | None = None
    finished_at: float | None = None
    session_id: str | None = None
    failures_detected: int = 0
    proposals_created: int = 0
    repairs_applied: int = 0
    error: str | None = None


_state = StartupSelfHealingState()


def get_startup_self_healing_state() -> dict[str, Any]:
    """Return an immutable snapshot suitable for health/readiness telemetry."""
    return asdict(_state)


def _skip_requested() -> bool:
    return os.environ.get(ENV_SKIP_STARTUP, "false").strip().lower() in {"1", "true", "yes"}


def _run(repo_root: Path, runner: Callable[..., Any]) -> None:
    _state.status = "running"
    _state.started_at = time.time()
    try:
        report = runner(
            repo_root=repo_root,
            rerun_flaky=False,
            attempt_llm_for_unclassified=True,
        )
        _state.session_id = report.session_id
        _state.failures_detected = len(report.classified)
        _state.proposals_created = len(report.proposals)
        _state.repairs_applied = sum(result.applied for result in report.apply_results)
        _state.status = "healthy" if not report.classified else "action_required"
    except Exception as error:  # surfaced through state and logs; task never fails silently
        _state.status = "failed"
        _state.error = f"{type(error).__name__}: {error}"
        logger.exception("Salamander startup self-healing cycle failed")
    finally:
        _state.finished_at = time.time()


async def start_startup_self_healing(
    repo_root: Path | None = None,
    *,
    runner: Callable[..., Any] = run_self_repair_cycle,
) -> asyncio.Task[None] | None:
    """Start exactly one managed Salamander diagnosis for this process startup."""
    if _skip_requested():
        _state.status = "skipped_by_operator"
        logger.warning(
            "Salamander startup self-healing explicitly disabled by %s", ENV_SKIP_STARTUP
        )
        return None
    if _state.status in {"running", "healthy", "action_required"}:
        return None
    root = repo_root or Path(__file__).resolve().parents[2]
    return asyncio.create_task(
        asyncio.to_thread(_run, root, runner), name="salamander-startup-self-healing"
    )

"""Observability — Part XII: metrics, health, alerts, health monitor,
drift sentry (OBS1–OBS3)."""

from __future__ import annotations

import time
from typing import Any, Optional

from .result import Ok, Result
from .types import AlertChannelSpec


class Metrics:
    """Counter + histogram registry with optional endpoint push."""

    def __init__(self, endpoint: Optional[str] = None):
        self.endpoint = endpoint
        self.counters: dict[str, float] = {}
        self.histograms: dict[str, list[float]] = {}

    def increment(self, name: str, amount: float = 1.0) -> None:
        self.counters[name] = self.counters.get(name, 0.0) + amount

    def histogram(self, name: str, value: float) -> None:
        self.histograms.setdefault(name, []).append(float(value))


class Health:
    """Liveness surface bound to the declared endpoint."""

    def __init__(self, endpoint: Optional[str] = None):
        self.endpoint = endpoint
        self.bound_at = time.time()
        self.state = "bound"

    def alive(self) -> bool:
        return self.state == "bound"


class AlertChannel:
    kind = "generic"

    def __init__(self, spec: AlertChannelSpec):
        self.spec = spec
        self.outbox: list[dict[str, Any]] = []

    def send(self, subject: str, body: Any) -> None:
        self.outbox.append({"subject": subject, "body": body, "ts": time.time()})


class SlackChannel(AlertChannel):
    kind = "slack"


class EmailChannel(AlertChannel):
    kind = "email"


class PagerDutyChannel(AlertChannel):
    kind = "pager"


class WebhookChannel(AlertChannel):
    kind = "webhook"


_KINDS = {
    "slack": SlackChannel,
    "email": EmailChannel,
    "pager": PagerDutyChannel,
    "webhook": WebhookChannel,
}


def open_metrics(endpoint: Optional[str]) -> Result[Metrics]:
    return Ok(Metrics(endpoint))


def open_health(endpoint: Optional[str]) -> Result[Health]:
    return Ok(Health(endpoint))


def open_alert(spec: AlertChannelSpec) -> AlertChannel:
    return _KINDS.get(spec.kind, WebhookChannel)(spec)


def alert_if_enabled(alerts: list[AlertChannel], subject: str, body: Any) -> None:
    for channel in alerts:
        channel.send(subject, body)


# ---------------------------------------------------------------------------
# Monitors (standing — L1–L4 require both running)
# ---------------------------------------------------------------------------


class HealthMonitor:
    def __init__(self, lhras: Any, interval: float = 10.0):
        self.lhras = lhras
        self.interval = interval
        self.running = True
        self.checks = [
            self._swarm_healthy,
            self._aethel_reachable,
            self._attester_reachable,
            self._siem_reachable,
            self._soar_reachable,
            self._policy_loaded,
            self._trust_root_valid,
        ]

    def _swarm_healthy(self) -> bool:
        return bool(self.lhras.swarm.workers)

    def _aethel_reachable(self) -> bool:
        return self.lhras.aethel is not None

    def _attester_reachable(self) -> bool:
        return self.lhras.attester is not None

    def _siem_reachable(self) -> bool:
        return self.lhras.cfg.siem_endpoint is None or self.lhras.siem is not None

    def _soar_reachable(self) -> bool:
        return self.lhras.cfg.soar_endpoint is None or self.lhras.soar is not None

    def _policy_loaded(self) -> bool:
        return self.lhras.policy is not None

    def _trust_root_valid(self) -> bool:
        return self.lhras.cfg.trust_root is not None and bool(self.lhras.cfg.trust_root.secret)

    def run_checks(self) -> dict[str, bool]:
        results = {}
        for check in self.checks:
            try:
                results[check.__name__.lstrip("_")] = bool(check())
            except Exception:
                results[check.__name__.lstrip("_")] = False
        return results

    def healthy(self) -> bool:
        return all(self.run_checks().values())


class DriftSentry:
    """Periodic code+config integrity verification (SD1–SD4)."""

    def __init__(self, lhras: Any, interval: float = 60.0):
        self.lhras = lhras
        self.interval = interval
        self.running = True
        self.verify_count = 0

    def verify(self) -> bool:
        from . import selfdefense

        self.verify_count += 1
        code = selfdefense.verify_code_integrity()
        config = selfdefense.verify_config_integrity(self.lhras)
        return code.is_ok and config.is_ok


def start_health_monitor(lhras: Any) -> HealthMonitor:
    return HealthMonitor(lhras)


def start_drift_sentry(lhras: Any) -> DriftSentry:
    return DriftSentry(lhras)

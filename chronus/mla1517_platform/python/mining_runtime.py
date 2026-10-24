"""PYTHIA's canonical hardware-to-Stratum mining runtime."""

from __future__ import annotations

import os
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_var] = "1"

import asyncio
import contextlib
import hashlib
import json
import logging
import signal
import sys
from dataclasses import replace
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PLATFORM_DIR = Path(__file__).resolve().parent
_CHRONOS_IGPU = _REPO_ROOT / "packages" / "chronos-one-igpu" / "src"
_PYTHIA_CONSUMER = _REPO_ROOT / "packages" / "pythia-consumer" / "src"
_TURING = _REPO_ROOT / "turing_universal_quantum_computer"
for _p in (str(_PLATFORM_DIR), str(_REPO_ROOT), str(_CHRONOS_IGPU), str(_PYTHIA_CONSUMER), str(_TURING)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from chronus.mla1517.hardware import MMIOBridge
from chronus.mla1517.mining.backend_registry import (
    BackendRegistry,
    BackendSelection,
    BackendUnavailable,
)
from chronus.mla1517.mining.m3_coordinator import M3PythiaProductionMiningCoordinator
from chronus.mla1517.mining.causal import CausalCoordinate
from chronus.mla1517.mining.retarget_telemetry import RetargetWindowTracker
from manifold_pool_coordinator import _build_parser, parse_endpoint
from worker_lifecycle import HeartbeatEmitter
from chronus.mla1517.mining.chain_observer import BitcoinChainObserver
from chronus.mla1517.mining.pool_chain import PoolChainObserver
from chronus.mla1517.mining.session import MiningSession
from chronus.mla1517.mining.stratum_events import StratumEventLog
from chronus.mla1517.mining.telemetry_history import (
    TelemetryHistory,
    default_history_path,
)
from manifold_pool_coordinator import PoolEndpoint
from salamander.runtime import MiningAutonomyBridge

LOG = logging.getLogger("pythia.mining_runtime")


def record_salamander_feedback(
    coordinator, storage_recorder, report: dict, previous_digest: str | None,
) -> tuple[str | None, bool]:
    """Custody changed SALAMANDER observations before EUCLID policy consumes them.

    Recording an observed diagnosis is not proof of completed healing.
    """
    classification = report.get("classification")
    if (
        storage_recorder is None
        or report.get("schema") != "salamander.runtime-autonomy.v1"
        or not isinstance(classification, dict)
        or classification.get("WIRED") is not True
        or not isinstance(report.get("evidence_head"), str)
        or not report["evidence_head"]
    ):
        return previous_digest, False
    summary = {
        "health": report.get("health"),
        "detected_issue": report.get("detected_issue"),
        "last_successful_healing_event": report.get("last_successful_healing_event"),
        "last_successful_optimisation": report.get("last_successful_optimisation"),
        "self_healing_evidenced": classification.get("SELF_HEALING") is True,
        "self_optimising_evidenced": classification.get("SELF_OPTIMISING") is True,
    }
    digest = hashlib.sha256(
        json.dumps(summary, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    if digest == previous_digest:
        return previous_digest, False
    coordinate = CausalCoordinate(
        **dict(getattr(coordinator, "_pending_correlation", None) or {})
    )
    coordinator.causal.record(
        "salamander_runtime_observed", coordinate,
        salamander_evidence_head=report["evidence_head"],
        source_evidence_custody=report.get("evidence_custody") or "UNAVAILABLE",
        observation_digest=digest,
        **summary,
    )
    # In strict mode CausalLedger's synchronous fail-closed observer is THESEUS.
    return digest, True


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def m3_required() -> bool:
    """Whether the runtime must enforce the complete M3 custody/security gate."""
    return _truthy(os.getenv("PYTHIA_M3_REQUIRED"))


# PYTHIA mines only through the pools in pool_catalog, resolved exactly as
# the control API's startup contract resolves them.
from pool_catalog import POOL_CATALOG, pool_names, pool_settings  # noqa: E402

# Tokens accepted inside PYTHIA_BACKEND_ORDER. The order is deliberately an
# operator policy, not an inferred benchmark ranking: capability probes prove
# a lane can execute, but they do not prove it is faster than every other lane.
_BACKEND_ORDER_TOKENS = frozenset(
    {"cpu", "gpu", "opencl", "cuda", "metal", "remote", "remote_gpu", "asic", "super_asic", "chronus", "one_igpu"}
)


def _catalog_pool(host: str) -> str | None:
    host = host.lower().rstrip(".")
    for name, entry in POOL_CATALOG.items():
        if any(host == d or host.endswith("." + d) for d in entry["domains"]):
            return name
    return None


def _endpoint(name: str, address: str, user: str, password: str, tls: bool) -> PoolEndpoint:
    parsed = parse_endpoint(address, name, tls=tls)
    pool = _catalog_pool(parsed.host)
    if pool is None and os.getenv("PYTHIA_ALLOW_UNLISTED_POOLS", "") != "1":
        raise SystemExit(
            f"{address!r} is not one of the configured mining pools "
            f"({', '.join(POOL_CATALOG)}); set PYTHIA_ALLOW_UNLISTED_POOLS=1 to override"
        )
    return PoolEndpoint(
        parsed.host,
        parsed.port,
        pool or name,
        parsed.tls,
        username=user,
        password=password,
        extranonce_subscribe=bool(POOL_CATALOG.get(pool or "", {}).get("extranonce_subscribe")),
        protocol=parsed.protocol,
    )


def pool_endpoints(args, config: dict | None = None) -> list[PoolEndpoint]:
    """Primary first, then failover, each with its own worker credentials."""
    if config is None:
        try:
            import runtime_config

            config = runtime_config.load()
        except Exception:
            LOG.debug("runtime_config unavailable", exc_info=True)
            config = {}
    configured = [
        p
        for p in config.get("pools", [])
        if isinstance(p, dict) and p.get("enabled", True) is not False
    ]
    if configured:
        ordered = sorted(configured, key=lambda p: not p.get("enabled"))
        return [
            _endpoint(
                f"pool{index}",
                p["endpoint"],
                p["worker"],
                p.get("password") or args.password,
                args.tls,
            )
            for index, p in enumerate(ordered)
        ]
    endpoints = []
    for index, name in enumerate(pool_names()):
        if name not in POOL_CATALOG:
            raise SystemExit(f"unknown pool {name!r}; choose from {', '.join(POOL_CATALOG)}")
        prefix = f"MLA1517_{name.upper()}"
        pool = pool_settings(
            name, primary=index == 0, fallback_user=args.user, fallback_password=args.password
        )
        if not pool.endpoint:
            raise SystemExit(f"{prefix}_ENDPOINT is required for {name}")
        if not pool.user:
            raise SystemExit(f"{prefix}_USER or --user is required for {name}")
        endpoints.append(_endpoint(name, pool.endpoint, pool.user, pool.password, args.tls))
    if not endpoints:
        raise SystemExit("no mining pool configured")
    return endpoints


def _registry() -> BackendRegistry:
    """The lane registry for this process; probes and decisions are evidence."""
    return BackendRegistry(
        software_revision=os.getenv("PYTHIA_SOFTWARE_REVISION", "unknown"),
        evidence_path=os.getenv("PYTHIA_BACKEND_EVIDENCE_PATH", "data/backend_decisions.jsonl"),
    )


def backend_order() -> tuple[str, ...] | None:
    """Return the declared auto-routing preference, if one is configured.

    ``PYTHIA_BACKEND_ORDER`` is a comma-separated preference list. Every item
    is still subject to BackendRegistry's real capability probe. CPU is not
    appended implicitly: if an operator intentionally omits it, exhausting
    the declared accelerator set fails closed instead of silently degrading.
    Duplicate aliases are collapsed while preserving the declared order.
    """
    raw = os.getenv("PYTHIA_BACKEND_ORDER", "").strip()
    if not raw:
        return None
    result: list[str] = []
    for item in raw.split(","):
        token = item.strip().lower()
        if not token:
            continue
        if token == "auto":
            raise SystemExit("PYTHIA_BACKEND_ORDER must list concrete backends, not 'auto'")
        if token not in _BACKEND_ORDER_TOKENS:
            raise SystemExit(
                f"PYTHIA_BACKEND_ORDER contains unknown backend {token!r}; "
                f"choose from {', '.join(sorted(_BACKEND_ORDER_TOKENS))}"
            )
        canonical = "remote" if token == "remote_gpu" else token
        # gpu and opencl are intentional aliases for the same registry lane;
        # keeping only the first prevents a duplicate probe/decision attempt.
        alias_key = "gpu" if canonical == "opencl" else canonical
        if any(("gpu" if prior == "opencl" else prior) == alias_key for prior in result):
            continue
        result.append(canonical)
    if not result:
        raise SystemExit("PYTHIA_BACKEND_ORDER must contain at least one concrete backend")
    return tuple(result)


def _record_aggregate_backend_selection(
    registry: BackendRegistry,
    selection: BackendSelection,
) -> None:
    """Persist the outer policy decision after concrete-lane attempts.

    ``BackendRegistry.select(<concrete lane>)`` already records each refusal or
    acceptance. A declared multi-lane ``auto`` policy needs one additional
    aggregate record so telemetry does not lose the original request and
    fallback provenance. BackendRegistry owns the append-only evidence format;
    this helper deliberately delegates to that recorder rather than writing a
    second file format.
    """
    recorder = getattr(registry, "_record", None)
    if callable(recorder):
        recorder(selection)
    else:  # small injected registries used by contract tests
        setattr(registry, "last_selection", selection)


def select_execution_backend(
    registry: BackendRegistry,
    requested: str,
    *,
    reprobe: bool = False,
    job_id: str = "Unavailable",
    epoch: str = "Unavailable",
) -> BackendSelection:
    """Bind one execution lane using declared policy and measured probes.

    Explicit ``requested`` lanes remain exact/fail-closed. ``auto`` preserves
    BackendRegistry's built-in policy unless ``PYTHIA_BACKEND_ORDER`` is set;
    when it is set, the concrete lanes are tried exactly in that order. Every
    concrete attempt is persisted by BackendRegistry and the final aggregate
    selection retains the original ``auto`` request, the refused-lane history,
    and whether the selected lane was a fallback. CPU is never appended behind
    the operator's back.
    """
    key = (requested or "auto").strip().lower()
    order = backend_order() if key == "auto" else None
    if order is None:
        return registry.select(key, reprobe=reprobe, job_id=job_id, epoch=epoch)

    refused: list[str] = []
    attempts: list[dict[str, str]] = []
    aggregate_probes = {}
    for index, token in enumerate(order):
        try:
            concrete = registry.select(
                token,
                reprobe=reprobe,
                job_id=job_id,
                epoch=epoch,
            )
        except BackendUnavailable as exc:
            refusal = f"{token}: {exc}"
            refused.append(refusal)
            attempts.append({"token": token, "outcome": "refused", "reason": str(exc)})
            last = getattr(registry, "last_selection", None)
            if isinstance(last, BackendSelection):
                aggregate_probes.update(last.probed)
            continue

        aggregate_probes.update(getattr(concrete, "probed", {}) or {})
        attempts.append(
            {
                "token": token,
                "outcome": "selected",
                "lane": concrete.lane,
                "reason": concrete.reason,
            }
        )
        reason = f"declared PYTHIA_BACKEND_ORDER {list(order)} selected {concrete.lane}" + (
            f" after refusals: {'; '.join(refused)}" if refused else ""
        )
        hasher = concrete.hasher
        if index > 0 and hasher is not None:
            # Preserve the fallback reason on hashers that expose this field;
            # this is diagnostic provenance only and never changes execution.
            try:
                hasher.fallback_reason = reason
            except Exception:
                pass
        aggregate = replace(
            concrete,
            requested=key,
            fallback=index > 0,
            reason=reason,
            probed=dict(aggregate_probes),
            observation={
                "requested": key,
                "policy_source": "PYTHIA_BACKEND_ORDER",
                "policy_order": list(order),
                "attempts": attempts,
                "probes": {name: probe.as_dict() for name, probe in aggregate_probes.items()},
            },
            available_actions=tuple(
                name for name, probe in aggregate_probes.items() if probe.available
            ),
            selected_action=concrete.lane,
            execution_target=concrete.lane,
            result="backend_bound",
            disposition="accepted",
        )
        _record_aggregate_backend_selection(registry, aggregate)
        return aggregate

    reason = "declared PYTHIA_BACKEND_ORDER exhausted with no available lane: " + "; ".join(refused)
    last = getattr(registry, "last_selection", None)
    if isinstance(last, BackendSelection):
        aggregate = replace(
            last,
            requested=key,
            fallback=False,
            reason=reason,
            probed=dict(aggregate_probes),
            observation={
                "requested": key,
                "policy_source": "PYTHIA_BACKEND_ORDER",
                "policy_order": list(order),
                "attempts": attempts,
                "probes": {name: probe.as_dict() for name, probe in aggregate_probes.items()},
            },
            available_actions=(),
            selected_action="Unavailable",
            execution_target="Unavailable",
            result="no_backend_bound",
            disposition="rejected",
        )
        _record_aggregate_backend_selection(registry, aggregate)
    raise BackendUnavailable(reason)


def _execution_hasher(backend: str, registry: BackendRegistry | None = None):
    """The hasher behind the Execution Router, bound through the registry.

    A lane is usable only after its real capability probe. ``auto`` uses the
    optional ``PYTHIA_BACKEND_ORDER`` policy when declared; otherwise it uses
    BackendRegistry's built-in policy. Explicit lanes select only that lane or
    fail closed. No unavailable lane is converted into fabricated capacity.
    """
    return select_execution_backend(registry or _registry(), backend).hasher


EXECUTION_DEVICES = (
    "auto",
    "opencl",
    "gpu",
    "cpu",
    "cuda",
    "metal",
    "remote",
    "asic",
    "super_asic",
    "chronus",
    "one_igpu",
)


def execution_device() -> str | None:
    """Bridge-free mining device from ``PYTHIA_EXECUTION_DEVICE``, if declared.

    ``opencl``/``gpu`` mines on the OpenCL device the hasher binds and
    self-checks against hashlib, and refuses to start without one;
    ``cuda``/``metal`` mine on the Chronus-owned native SHA-256d lanes
    (CuPy CUDA runtime / MLX on Apple GPU), each self-checked against
    hashlib at bind with no CPU or OpenCL substitution; ``cpu``
    mines on the labelled CPU reference; ``remote`` mines on a remote GPU
    agent bound via ``MLA1517_REMOTE_GPU_ENDPOINT``; ``asic`` binds a real
    ASIC channel (``HYBRID_ASIC_ENDPOINT``/``HYBRID_ASIC_SERIAL``/
    ``HYBRID_ASIC_PCIE``) or fails closed; ``super_asic`` binds the hybrid
    composition over every supported substrate (ASIC channel + remote fleet
    + resident GPU/CPU solver) via the Lucas-partitioned coordinator;
    ``auto`` probes according to the declared backend policy. Unset keeps the
    MMIO bridge as the only device.
    """
    value = os.getenv("PYTHIA_EXECUTION_DEVICE", "").strip().lower()
    if not value:
        return None
    if value not in EXECUTION_DEVICES:
        raise SystemExit(f"PYTHIA_EXECUTION_DEVICE must be one of {', '.join(EXECUTION_DEVICES)}")
    return value


def assert_declared_chain(observer: BitcoinChainObserver | None) -> None:
    """Startup validation: a declared network must match the configured node."""
    expected = os.getenv("PYTHIA_BITCOIN_NETWORK", "").strip().lower()
    if not expected:
        return
    if observer is None:
        raise SystemExit("PYTHIA_BITCOIN_NETWORK is set but PYTHIA_BITCOIN_RPC_URL is not")
    try:
        observer.assert_chain(expected)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    LOG.info("Bitcoin chain confirmed: %s", expected)


async def _main_async(args) -> None:
    device = execution_device()
    if not args.device and device is None:
        raise SystemExit(
            "--device or MLA1517_MMIO_DEVICE is required "
            "(or PYTHIA_EXECUTION_DEVICE=opencl|cpu|cuda|metal|remote|asic|super_asic for bridge-free mining)"
        )
    # The supervisor exports PYTHIA_IDENTITY_HMAC_SECRET to every spawned
    # worker. A standalone --mine process has no supervisor to provision one.
    os.environ.setdefault("PYTHIA_IDENTITY_HMAC_SECRET", os.urandom(32).hex())
    backend = device if not args.device else os.getenv("PYTHIA_EXECUTION_BACKEND", "auto")
    strict_m3 = m3_required()
    if args.submit and not strict_m3:
        raise SystemExit(
            "live --submit refused: PYTHIA_M3_REQUIRED=1 is mandatory "
            "for AL HARAS authorisation and THESEUS proof custody"
        )
    endpoints = pool_endpoints(args)
    observer = BitcoinChainObserver.from_environment()
    assert_declared_chain(observer)
    session = MiningSession(
        os.getenv("PYTHIA_MINING_SESSION_PATH", "data/mining_session.json"),
        cooldown_seconds=float(os.getenv("PYTHIA_MINING_COOLDOWN_SECONDS", "1")),
    )
    try:
        with HeartbeatEmitter("agentic-mining") as heartbeat:
            storage_recorder = None
            m3_gate = None
            history = TelemetryHistory(default_history_path())
            stratum_events = StratumEventLog(on_event=history.append)
            retarget = RetargetWindowTracker(
                os.getenv("PYTHIA_RETARGET_TELEMETRY_PATH", "data/retarget_windows.json")
            )
            autonomy = MiningAutonomyBridge.from_environment()
            last_salamander_feedback_digest: str | None = None

            def publish_stratum_status(snapshot: dict) -> None:
                enriched = dict(snapshot)
                window = retarget.observe(enriched)
                enriched["retarget_window"] = window
                if window is not None:
                    enriched["effective_stratum_hashrate_hs"] = window.get(
                        "effective_stratum_hashrate_hs"
                    )
                stratum_events.observe(enriched)
                heartbeat.report(
                    stratum_status=json.dumps(
                        enriched,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    stratum_events=json.dumps(
                        stratum_events.payload(), sort_keys=True, separators=(",", ":")
                    ),
                )

            def publish_mining_evidence(snapshot: dict) -> None:
                nonlocal last_salamander_feedback_digest
                try:
                    autonomy_snapshot = autonomy.observe_mining_snapshot(snapshot)
                except Exception as exc:
                    LOG.exception("Salamander runtime evidence bridge failed")
                    autonomy_snapshot = {
                        "schema": "salamander.runtime-autonomy.v1",
                        "health": "UNAVAILABLE",
                        "evidence_source": "Unavailable",
                        "reason": type(exc).__name__,
                    }

                # Strict M3 custodies meaningful SALAMANDER observations
                # before they influence EUCLID's next bounded mining decision.
                try:
                    digest, recorded = record_salamander_feedback(
                        coordinator, storage_recorder, autonomy_snapshot,
                        last_salamander_feedback_digest,
                    )
                    last_salamander_feedback_digest = digest
                    autonomy_snapshot = {
                        **autonomy_snapshot,
                        "pythia_theseus_observation": (
                            "RECORDED" if recorded else
                            ("UNCHANGED" if digest else "UNAVAILABLE")
                        ),
                    }
                except Exception as exc:
                    LOG.exception("SALAMANDER -> THESEUS mining observation failed")
                    if strict_m3:
                        coordinator._block_m3(
                            f"SALAMANDER_OBSERVATION_CUSTODY_FAILURE:{type(exc).__name__}"
                        )
                    autonomy_snapshot = {
                        **autonomy_snapshot,
                        "pythia_theseus_observation": "FAILED",
                    }

                # SALAMANDER owns remediation; PYTHIA correlates its evidence,
                # EUCLID advises only within PYTHIA's dispatch breadth.
                try:
                    coordinator.record_salamander_autonomy(autonomy_snapshot)
                except Exception:
                    LOG.exception("Could not correlate Salamander evidence with PYTHIA cycle")

                enriched = dict(snapshot)
                enriched["euclid_support"] = coordinator.euclid_support.snapshot()
                try:
                    current_cycle = coordinator.pythia_authority.snapshot().get("agentic_mining")
                    if current_cycle is not None:
                        enriched["agentic_mining"] = current_cycle
                except Exception:
                    LOG.exception("Could not refresh PYTHIA agentic evidence after Salamander")
                enriched["salamander_autonomy"] = autonomy_snapshot
                storage_health = (
                    # Status report: new rows only, prior failures carried
                    # forward; the lease gate owns the timed full pass.
                    storage_recorder.health(reconcile=False, full=False)
                    if storage_recorder is not None
                    else {
                        "schema": "pythia.m3-storage-health/1",
                        "configured": False,
                        "strict": strict_m3,
                        "healthy": False,
                        "reason": "storage recorder not configured",
                    }
                )
                authorization = (
                    m3_gate.status()
                    if m3_gate is not None
                    else {
                        "schema": "pythia.m3-authorization/1",
                        "configured": False,
                    }
                )
                runtime_m3 = coordinator.m3_status()

                heartbeat.report(
                    mining_evidence=json.dumps(
                        enriched, sort_keys=True, separators=(",", ":"), default=str
                    ),
                    salamander_autonomy=json.dumps(
                        autonomy_snapshot,
                        sort_keys=True,
                        separators=(",", ":"),
                        default=str,
                    ),
                    m3_storage=json.dumps(
                        storage_health, sort_keys=True, separators=(",", ":"), default=str
                    ),
                    m3_authorization=json.dumps(
                        authorization, sort_keys=True, separators=(",", ":"), default=str
                    ),
                    m3_runtime=json.dumps(
                        runtime_m3, sort_keys=True, separators=(",", ":"), default=str
                    ),
                )

            os.environ.setdefault("PYTHIA_INTELLIGENCE_DIR", "data/intelligence")
            registry = _registry()
            selection = select_execution_backend(registry, backend)
            LOG.info(
                "execution backend selected requested=%s lane=%s fallback=%s reason=%s",
                backend,
                selection.lane,
                selection.fallback,
                selection.reason,
            )
            username = args.user or endpoints[0].username

            from chronus.mla1517.mining.storage_recorder import MiningStorageRecorder
            from m3_mining_guard import M3MiningSubmissionGate

            storage_recorder = MiningStorageRecorder.from_env(
                worker=username,
                strict=strict_m3,
            )
            if strict_m3:
                if storage_recorder is None:  # defensive; strict from_env raises first
                    raise SystemExit("strict M3 mode requires THESEUS storage")
                initial_storage_health = storage_recorder.health(reconcile=True)
                if initial_storage_health.get("healthy") is not True:
                    raise SystemExit(
                        "M3 storage/reconciliation gate failed: "
                        + str(initial_storage_health.get("unresolved") or initial_storage_health)
                    )
                try:
                    m3_gate = M3MiningSubmissionGate.from_env(storage_recorder)
                except Exception as exc:
                    raise SystemExit(f"M3 AL HARAS gate unavailable: {exc}") from exc
                if not m3_gate.configured():
                    raise SystemExit(
                        "M3 AL HARAS gate is not fully configured/durable"
                    )

            coordinator = M3PythiaProductionMiningCoordinator(
                endpoints,
                username=username,
                password=args.password,
                submit_enabled=args.submit,
                mining_session=session,
                chain_observer=observer,
                stratum_status_sink=publish_stratum_status,
                execution_hasher=selection.hasher,
                # Salamander restarts re-select through the same declared
                # policy, so a failed lane is re-probed and rerouted only to
                # an allowed alternative.
                execution_hasher_factory=(
                    lambda: select_execution_backend(registry, backend, reprobe=True).hasher
                ),
                backend_registry=registry,
                causal_log_path=os.getenv("PYTHIA_CAUSAL_LOG_PATH", "data/causal_ledger.jsonl"),
                m3_required=strict_m3,
                m3_gate=m3_gate,
                # Production compute and network submission are independent:
                # locally verified candidates enter the coordinator's bounded,
                # freshness-checked single-writer queue instead of parking the
                # hashing loop on pool acknowledgement latency.
                asynchronous_submission=True,
            )
            if coordinator.chain_observer is None:
                coordinator.chain_observer = PoolChainObserver(lambda: coordinator.client)
                LOG.info("chain evidence: pool Stratum jobs (no bitcoind configured)")
            if storage_recorder is not None:
                coordinator.causal.set_observer(
                    storage_recorder.observe,
                    fail_closed=strict_m3,
                )
                LOG.info(
                    "M3 storage plane recording tenant=%s root=%s strict=%s",
                    storage_recorder.tenant_id,
                    storage_recorder.root,
                    strict_m3,
                )
                storage_health = storage_recorder.health(reconcile=True)
            else:
                storage_health = {
                    "schema": "pythia.m3-storage-health/1",
                    "configured": False,
                    "strict": False,
                    "healthy": False,
                    "reason": "storage recorder not configured",
                }
            heartbeat.report(
                m3_storage=json.dumps(
                    storage_health, sort_keys=True, separators=(",", ":"), default=str
                ),
                m3_authorization=json.dumps(
                    (
                        m3_gate.status()
                        if m3_gate is not None
                        else {
                            "schema": "pythia.m3-authorization/1",
                            "configured": False,
                        }
                    ),
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ),
                m3_runtime=json.dumps(
                    coordinator.m3_status(),
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ),
            )
            coordinator.set_evidence_sink(publish_mining_evidence)
            coordinator.set_metrics_sink(
                lambda counters: (
                    heartbeat.report(**counters),
                    history.record_metrics(counters),
                )
            )
            coordinator.set_agentic_state_path(
                os.getenv("PYTHIA_AGENTIC_STATE_PATH", "data/agentic_policy.json")
            )
            try:
                publish_stratum_status({
                    "state": "CONNECTING",
                    "status": "connecting",
                    "connected": False,
                    "primary": {
                        "pool_id": getattr(endpoints[0], "name", "braiins"),
                        "endpoint": getattr(endpoints[0], "endpoint", str(endpoints[0])),
                        "configured": True,
                    },
                })
            except Exception:
                pass
            if not args.device:
                hasher = coordinator.execution_hasher
                LOG.info(
                    "bridge-free mining: device=%s backend=%s hasher_device=%s",
                    device,
                    getattr(hasher, "backend", None),
                    getattr(hasher, "device", None),
                )
                max_backoff = float(os.getenv("PYTHIA_RECONNECT_MAX_S", "30"))
                await coordinator.run_execution_loop(max_backoff_s=max_backoff)
                return
            with MMIOBridge(args.device, map_bytes=args.map_bytes) as bridge:
                await coordinator.run_hardware_loop(
                    bridge,
                    difficulty_mask=args.difficulty_mask,
                    base_step=args.base_step,
                )
    finally:
        session.close()


async def _run_with_signals(args) -> None:
    """Cancel the miner cooperatively on SIGINT/SIGTERM."""
    loop = asyncio.get_running_loop()
    task = asyncio.create_task(_main_async(args), name="pythia-mining-runtime")
    installed: list[signal.Signals] = []

    def request_shutdown(sig: signal.Signals) -> None:
        LOG.info("received %s; shutting down mining runtime", sig.name)
        task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_shutdown, sig)
        except (NotImplementedError, RuntimeError, ValueError):
            continue
        installed.append(sig)
    try:
        await task
    except asyncio.CancelledError:
        if not task.cancelled():
            raise
    finally:
        for sig in installed:
            with contextlib.suppress(NotImplementedError, RuntimeError, ValueError):
                loop.remove_signal_handler(sig)


def main() -> None:
    args = _build_parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(_run_with_signals(args))


if __name__ == "__main__":
    main()

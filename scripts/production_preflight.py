#!/usr/bin/env python3
"""Fail-explicit PYTHIA release preflight.

This script performs no mining, network connection, share submission, or secret
printing.  It separates application, device, and live-pool prerequisites and
reports PASS/BLOCKED/FAIL as machine-readable JSON.
"""

from __future__ import annotations

import argparse
import importlib
import hashlib
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

REQUIRED_MODULES = (
    "chronus.mla1517.mining.coordinator",
    "control_api",
    "system_fabric",
)
LIVE_REQUIRED_ENV = (
    "MLA1517_STRATUM_USER",
    "MLA1517_STRATUM_PASSWORD",
)
LIVE_STORAGE_ENV = (
    "PYTHIA_STORAGE_DB",
    "PYTHIA_STORAGE_ROOT",
    "PYTHIA_STORAGE_CUSTODY_ROOT",
    "PYTHIA_STORAGE_TENANT",
    "PYTHIA_STORAGE_INTEGRITY_KEY_HEX",
    "PYTHIA_STORAGE_CUSTODY_KEY_HEX",
    "PYTHIA_M3_ACTOR",
    "PYTHIA_M3_AL_HARAS_TOKEN",
)
TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Check:
    name: str
    state: str
    detail: str


def _truthy(value: str | None) -> bool:
    return bool(value and value.strip().lower() in TRUE_VALUES)


def _application_checks(
    *,
    importer: Callable[[str], object],
    runtime_config: Path,
    modules: Sequence[str],
) -> list[Check]:
    checks: list[Check] = []
    checks.append(
        Check(
            "python_version",
            "PASS" if sys.version_info >= (3, 10) else "FAIL",
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        )
    )
    for module in modules:
        try:
            importer(module)
        except Exception as exc:  # exact import defect is evidence
            checks.append(Check(f"import:{module}", "FAIL", f"{type(exc).__name__}: {exc}"))
        else:
            checks.append(Check(f"import:{module}", "PASS", "importable"))
    parent = runtime_config.expanduser().resolve().parent
    if not parent.exists():
        checks.append(Check("runtime_config_parent", "BLOCKED", f"missing directory: {parent}"))
    elif not os.access(parent, os.W_OK):
        checks.append(Check("runtime_config_parent", "BLOCKED", f"not writable: {parent}"))
    else:
        checks.append(Check("runtime_config_parent", "PASS", f"writable: {parent}"))
    return checks


def _default_opencl_probe() -> tuple[int, str]:
    try:
        import pyopencl as cl  # type: ignore
    except Exception as exc:
        return 0, f"pyopencl unavailable: {type(exc).__name__}: {exc}"
    try:
        devices = [device for platform in cl.get_platforms() for device in platform.get_devices()]
    except Exception as exc:
        return 0, f"OpenCL enumeration failed: {type(exc).__name__}: {exc}"
    return len(devices), f"{len(devices)} OpenCL device(s)"


def _device_checks(
    env: Mapping[str, str], opencl_probe: Callable[[], tuple[int, str]]
) -> list[Check]:
    backend = env.get("MLA1517_GPU_BACKEND", "").strip().lower()
    if backend != "opencl":
        return [
            Check(
                "device_backend",
                "BLOCKED",
                "set MLA1517_GPU_BACKEND=opencl for the production device gate",
            )
        ]
    count, detail = opencl_probe()
    return [
        Check("device_backend", "PASS", "opencl"),
        Check("opencl_devices", "PASS" if count > 0 else "BLOCKED", detail),
    ]


def _live_checks(env: Mapping[str, str]) -> list[Check]:
    checks: list[Check] = []
    for name in LIVE_REQUIRED_ENV:
        checks.append(Check(f"env:{name}", "PASS" if env.get(name) else "BLOCKED", "configured" if env.get(name) else "missing"))
    endpoint = env.get("MLA1517_BRAIINS_ENDPOINT") or env.get("MLA1517_STRATUM_ENDPOINT")
    checks.append(Check("pool_endpoint", "PASS" if endpoint else "BLOCKED", "configured" if endpoint else "missing"))
    strict = _truthy(env.get("PYTHIA_M3_REQUIRED"))
    checks.append(Check(
        "strict_m3",
        "PASS" if strict else "BLOCKED",
        "required for canonical AL HARAS + THESEUS submission",
    ))
    for name in LIVE_STORAGE_ENV:
        configured = bool(env.get(name))
        if name.endswith("_KEY_HEX") and configured:
            try:
                configured = len(bytes.fromhex(env[name])) >= 32
            except ValueError:
                configured = False
        checks.append(Check(
            f"m3:{name}", "PASS" if configured else "BLOCKED",
            "configured" if configured else "missing or invalid",
        ))
    # The historical HYBA_ENABLE_* variables gate the legacy bridge ONLY.
    # The canonical miner instead uses runtime_config's exact pool-identity
    # approval plus the M3 coordinator. Never qualify canonical live through
    # the bridge environment triple-gate.
    path = Path(env.get("PYTHIA_RUNTIME_CONFIG", "data/runtime_config.json"))
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
        enabled = cfg.get("live_submit", {}).get("enabled") is True
        approved = str(cfg.get("live_submit", {}).get("approval_id") or "")
        active = next(
            (p for p in cfg.get("pools", []) if p.get("enabled") is True),
            None,
        )
        bound = bool(active) and approved == hashlib.sha256(
            f"{active['endpoint']}|{active['worker']}".encode()
        ).hexdigest()
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        enabled = False
        bound = False
    checks.append(Check(
        "canonical_pool_identity_approval",
        "PASS" if enabled and bound else "BLOCKED",
        "bound to active endpoint + worker" if enabled and bound
        else "runtime approval missing, malformed or not bound",
    ))
    return checks


TRAINING_EPOCH_LIMIT = 100
TRAINING_CASE_LIMIT = 2000


def _training_checks(*, epochs: int, cases: int, seed: int) -> list[Check]:
    """Bounded train/evaluate/verify cycle on the mining-shaped task.

    Runs the governed pipeline end to end inside a temp directory: real
    ExperienceSuperlearner training, sealed manifest, checkpoint restore
    equivalence, durable replay rejection and the mining-adapter handoff.
    """
    import tempfile

    if not 1 <= epochs <= TRAINING_EPOCH_LIMIT:
        return [Check("training_epochs", "FAIL", f"epochs must be in [1,{TRAINING_EPOCH_LIMIT}]")]
    if not 4 <= cases <= TRAINING_CASE_LIMIT:
        return [Check("training_cases", "FAIL", f"cases per partition must be in [4,{TRAINING_CASE_LIMIT}]")]
    checks: list[Check] = []
    repo_root = Path(__file__).resolve().parents[1]
    platform = repo_root / "chronus" / "mla1517_platform" / "python"
    for extra in (str(platform), str(repo_root)):
        if extra not in sys.path:
            sys.path.insert(0, extra)
    try:
        from euclid.checkpoint_manifest import load_manifest, verify_manifest
        from euclid.learning_service import LearningService
        from euclid.memory_database import MemoryDatabase
        from euclid.mining_training_task import (
            breadth_reward,
            make_partitioned_dataset,
        )
        from euclid.training_pipeline import TrainingPipeline
        from hyba_substrate.euclid_experience_superlearner import (
            ExperienceSuperlearner,
        )
        checks.append(Check("training_imports", "PASS", "governed training modules importable"))
    except Exception as exc:
        return [Check("training_imports", "FAIL", f"{type(exc).__name__}: {exc}")]
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
        root = Path(directory)
        checkpoint = root / "learner.json"
        manifest_path = root / "manifest.json"
        report_path = root / "training_report.json"
        journal_path = root / "replay_journal.json"
        database = MemoryDatabase(root / "memory.sqlite3")
        try:
            dataset = make_partitioned_dataset(per_partition=cases)
            learner = ExperienceSuperlearner(checkpoint, epsilon=0.2, seed=seed)
            service = LearningService(
                experience_learner=learner,
                memory_database=database,
                replay_journal_path=journal_path,
            )
            pipeline = TrainingPipeline(
                learner,
                service,
                mission_id="preflight-training",
                provenance="sha256:preflight",
            )
            report = pipeline.run(
                task_id="bitcoin-mining-operating-breadth",
                actions=("hold", "reduce", "restore"),
                train_cases=dataset["train"],
                validation_cases=dataset["validation"],
                final_test_cases=dataset["final_test"],
                reward=breadth_reward,
                epochs=epochs,
                control_seed=seed,
                report_path=report_path,
                manifest_path=manifest_path,
                source_revision="preflight",
            )
            checks.append(Check(
                "training_pipeline",
                "PASS" if report.passed else "FAIL",
                f"trained_mean={report.trained_mean:.3f} baseline={report.baseline_mean:.3f} "
                f"fixed={report.fixed_action_mean:.3f} uninformed={report.uninformed_mean:.3f}",
            ))
            controls = set(report.controls)
            checks.append(Check(
                "named_controls",
                "PASS" if controls == {"current_policy_baseline", "fixed_action", "uninformed"} else "FAIL",
                f"controls={sorted(controls)} seed={report.control_seed}",
            ))
        except Exception as exc:
            checks.append(Check("training_pipeline", "FAIL", f"{type(exc).__name__}: {exc}"))
            database.close()
            return checks
        try:
            manifest = load_manifest(manifest_path)
            verify_manifest(manifest, learner_checkpoint_path=checkpoint, evidence_path=report_path)
            checks.append(Check("manifest_roundtrip", "PASS", f"seal verified revision={manifest['source_revision']}"))
        except Exception as exc:
            checks.append(Check("manifest_roundtrip", "FAIL", f"{type(exc).__name__}: {exc}"))
        try:
            restored = ExperienceSuperlearner(checkpoint)
            same_q = restored.q_values == learner.q_values
            states = [dict(case.state) for case in dataset["validation"]]
            same_actions = all(
                restored.select_action("bitcoin-mining-operating-breadth", state, explore=False)
                == learner.select_action("bitcoin-mining-operating-breadth", state, explore=False)
                for state in states
            )
            checks.append(Check(
                "restore_equivalence",
                "PASS" if same_q and same_actions else "FAIL",
                "restored q-values and deterministic decisions match",
            ))
        except Exception as exc:
            checks.append(Check("restore_equivalence", "FAIL", f"{type(exc).__name__}: {exc}"))
        try:
            from chronus.mla1517.mining.euclid_support import EuclidMiningSupport

            support = EuclidMiningSupport(
                64, state_path=str(checkpoint), manifest_path=str(manifest_path)
            )
            identity = support.snapshot().get("policy_identity") or {}
            checks.append(Check(
                "mining_handoff",
                "PASS" if support.available and identity.get("manifest_verified") else "FAIL",
                f"adapter consumes verified checkpoint {identity.get('checkpoint_sha256', '')[:12]}",
            ))
        except Exception as exc:
            checks.append(Check("mining_handoff", "FAIL", f"{type(exc).__name__}: {exc}"))
        try:
            from euclid.contracts import Experience, RewardAuthority

            # A fresh replay id legitimately records once (mutating the
            # checkpoint) so the restart can prove the same id is rejected.
            replayed = Experience(
                experience_id="preflight-replay",
                mission_id="preflight-training",
                domain="bitcoin-mining-operating-breadth",
                source="preflight",
                observation={"rejected_band": 3},
                action="reduce",
                outcome={},
                reward=-1.0,
                reward_authority=RewardAuthority.VALIDATED_SIMULATION,
                provenance="sha256:preflight",
                uncertainty=0.0,
                replay_id="preflight-replay-1",
            )
            service.record(replayed)
            restarted = LearningService(
                experience_learner=ExperienceSuperlearner(checkpoint),
                replay_journal_path=journal_path,
            )
            transitions_before = len(restarted.experience_learner.transitions)
            rejected = False
            try:
                restarted.record(replayed)
            except ValueError:
                rejected = True
            not_rewarded_twice = len(restarted.experience_learner.transitions) == transitions_before
            checks.append(Check(
                "durable_replay_rejection",
                "PASS" if rejected and not_rewarded_twice else "FAIL",
                "replay after restart rejected before learner mutation",
            ))
        except Exception as exc:
            checks.append(Check("durable_replay_rejection", "FAIL", f"{type(exc).__name__}: {exc}"))
        database.close()
    return checks


def evaluate(
    profile: str,
    *,
    env: Mapping[str, str] | None = None,
    importer: Callable[[str], object] = importlib.import_module,
    opencl_probe: Callable[[], tuple[int, str]] = _default_opencl_probe,
    modules: Sequence[str] = REQUIRED_MODULES,
    training_options: Mapping[str, int] | None = None,
) -> dict[str, object]:
    if profile not in {"application", "device", "live", "training"}:
        raise ValueError(f"unknown profile: {profile}")
    env = dict(os.environ if env is None else env)
    if profile == "training":
        options = dict(training_options or {})
        checks = _training_checks(
            epochs=int(options.get("epochs", 3)),
            cases=int(options.get("cases", 12)),
            seed=int(options.get("seed", 20260718)),
        )
    else:
        runtime_config = Path(env.get("PYTHIA_RUNTIME_CONFIG", "data/runtime_config.json"))
        checks = _application_checks(importer=importer, runtime_config=runtime_config, modules=modules)
        if profile in {"device", "live"}:
            checks.extend(_device_checks(env, opencl_probe))
        if profile == "live":
            checks.extend(_live_checks(env))
    states = {check.state for check in checks}
    overall = "FAIL" if "FAIL" in states else "BLOCKED" if "BLOCKED" in states else "PASS"
    return {
        "schema": "pythia.production_preflight/1",
        "profile": profile,
        "state": overall,
        "side_effects": "none",
        "checks": [asdict(check) for check in checks],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("application", "device", "live", "training"), default="application")
    parser.add_argument("--strict", action="store_true", help="exit non-zero on BLOCKED as well as FAIL")
    parser.add_argument("--output", type=Path, help="optional JSON evidence file")
    parser.add_argument("--epochs", type=int, default=3, help="training profile: epochs (bounded)")
    parser.add_argument("--cases", type=int, default=12, help="training profile: cases per partition (bounded)")
    parser.add_argument("--seed", type=int, default=20260718, help="training profile: control/learner seed")
    args = parser.parse_args(argv)
    report = evaluate(
        args.profile,
        training_options={"epochs": args.epochs, "cases": args.cases, "seed": args.seed},
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    if report["state"] == "FAIL":
        return 1
    if args.strict and report["state"] == "BLOCKED":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

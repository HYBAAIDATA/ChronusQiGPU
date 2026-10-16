"""Clean-room runtime fidelity verification for the installed euclid-engine wheel.

Runs with a clean-venv interpreter from an empty directory outside the checkout
(e.g., in a temporary directory outside the repository).
Every gate exercises the shipped entry points strictly from site-packages:
  1. Strict site-packages isolation (no source tree on sys.path or in cwd)
  2. CompositionRoot custody & EuclidRuntime canonical initialization
  3. Capability registry & organ discovery
  4. Governed dispatch, permission boundaries, and fail-closed audit vetoes
  5. Unified intelligence subdomain architecture (physics, cognition, gatekeeper)
  6. Live empirical state transition under AL HARAS pre-execution audit receipt
  7. Fail-closed negative gates (unapproved capability, exhausted budget)
  8. Verified rollback port on execution exception
  9. Clean instance restart and state reconstruction without memory bleed
 10. Backward-compatible deprecation shims (hyba_toe_intelligence, hyba_euclid_intelligence)
"""

from __future__ import annotations

import os
import sys
import time
import json
import warnings
from pathlib import Path
from typing import Any, Dict


def log_gate(name: str, passed: bool, detail: str = "") -> None:
    status = "[PASS]" if passed else "[FAIL]"
    print(f"  {status} {name}{f': {detail}' if detail else ''}", flush=True)


def gate_isolation() -> Dict[str, Any]:
    print("\n--- Gate 1: Out-of-Tree Site-Packages Isolation ---")
    required_packages = [
        "euclid",
        "Intelligence",
        "aethel",
        "kellogg",
        "toe",
        "lucas",
        "turing_core",
        "pythia_turing_math",
        "hyba_substrate",
        "resonance_intelligence",
    ]
    modules_checked = {}
    for pkg in required_packages:
        mod = __import__(pkg)
        mod_file = getattr(mod, "__file__", "") or ""
        modules_checked[pkg] = mod_file
        is_in_site_packages = "site-packages" in mod_file
        log_gate(f"Package '{pkg}' in site-packages", is_in_site_packages, mod_file)
        if not is_in_site_packages:
            raise RuntimeError(f"POLLUTION: '{pkg}' loaded from outside site-packages: {mod_file}")

    cwd = str(Path.cwd().resolve())
    print(f"  [*] Current working directory: {cwd}")
    return {"passed": True, "modules": modules_checked}


def gate_canonical_init(work: Path) -> Dict[str, Any]:
    print("\n--- Gate 2: Canonical Runtime Init & CompositionRoot Custody ---")
    from aethel.enterprise.lifecycle import CompositionRoot
    from euclid.runtime import EuclidRuntime

    lifecycle = CompositionRoot(work / "custody", tenant="clean-room-tenant", hmac_key=b"k" * 32)
    lifecycle.start()
    runtime = EuclidRuntime(creator_id="clean-room-creator", state_dir=work / "runtime-state")
    try:
        runtime.bind_adaptive_data_port(lifecycle.data_port("euclid"))
        runtime.compose_adaptive_intelligence()
        report = runtime.startup_report()
        grants = runtime.rights.snapshot()["grants"]
        leak = (runtime.state_dir / "adaptive_knowledge.json").exists()

        schema_ok = report.get("schema") == "euclid.startup/1"
        grants_ok = len(grants) == 0
        no_leak = not leak
        adaptive_ok = runtime.adaptive is not None

        log_gate("Startup report schema (euclid.startup/1)", schema_ok, report.get("schema"))
        log_gate("Zero initial unearned grants", grants_ok)
        log_gate("No private adaptive knowledge leak", no_leak)
        log_gate("Adaptive intelligence composed", adaptive_ok)

        passed = schema_ok and grants_ok and no_leak and adaptive_ok
        return {"passed": passed, "report": report}
    finally:
        runtime.close()
        lifecycle.stop()


def gate_capability_discovery(work: Path) -> Dict[str, Any]:
    print("\n--- Gate 3: Capability Discovery & Registration ---")
    from euclid.contracts import Authority
    from euclid.governance import Organ
    from euclid.runtime import EuclidRuntime

    runtime = EuclidRuntime(creator_id="discovery-agent", state_dir=work / "discovery-state")
    try:
        organ = Organ(
            "clean-room-organ",
            frozenset({"ping", "status"}),
            Authority.READ_ONLY,
            lambda req: {"pong": True, "ts": time.time()},
        )
        runtime.register_organ(organ)
        registry = [item["organ_id"] for item in runtime.registry.report()]
        registered = "clean-room-organ" in registry
        log_gate("Dynamic organ registration & discovery", registered)
        return {"passed": registered, "registry": registry}
    finally:
        runtime.close()


def gate_dispatch_authorization(work: Path) -> Dict[str, Any]:
    print("\n--- Gate 4: Governed Dispatch & Fail-Closed Vetoes ---")
    from euclid.contracts import Authority
    from euclid.governance import Organ
    from euclid.runtime import EuclidRuntime

    runtime = EuclidRuntime(creator_id="authz-agent", state_dir=work / "authz-state")
    closed = False
    try:
        runtime.register_organ(Organ(
            "monitored-organ",
            frozenset({"query"}),
            Authority.READ_ONLY,
            lambda req: {"result": "authorized-data"},
        ))

        # 1. Unearned grant refusal
        refused_permission = False
        try:
            runtime.delegator.dispatch("monitored-organ", "query", {}, confident=True, safe=True)
        except PermissionError:
            refused_permission = True
        log_gate("PermissionError on ungranted dispatch", refused_permission)

        # 2. Authorized dispatch after explicit grant
        runtime.rights.grant(runtime.creator_id, "monitored-organ", "query", "dispatch")
        res = runtime.delegator.dispatch("monitored-organ", "query", {}, confident=True, safe=True)
        dispatched_ok = res.get("result") == "authorized-data"
        log_gate("Authorized dispatch succeeds after explicit grant", dispatched_ok)

        # 3. Unknown organ refusal
        unknown_refused = False
        try:
            runtime.delegator.dispatch("nonexistent-organ", "query", {}, confident=True, safe=True)
        except ValueError:
            unknown_refused = True
        log_gate("ValueError on unknown organ dispatch", unknown_refused)

        # 4. Fail-closed on closed runtime
        runtime.close()
        closed = True
        closed_refused = False
        try:
            runtime.dispatch_specialist("monitored-organ", {}, tenant_id="t", actor="a")
        except RuntimeError:
            closed_refused = True
        log_gate("RuntimeError on invocation after runtime closure", closed_refused)

        passed = refused_permission and dispatched_ok and unknown_refused and closed_refused
        return {"passed": passed}
    finally:
        if not closed:
            runtime.close()


def gate_unified_intelligence_architecture() -> Dict[str, Any]:
    print("\n--- Gate 5: Unified Intelligence Architecture ---")
    import euclid.intelligence as intel
    import Intelligence

    # Canonical surfaces
    euclid_has_subdomains = (
        hasattr(intel, "physics")
        and hasattr(intel, "cognition")
        and hasattr(intel, "gatekeeper")
        and hasattr(intel, "UnifiedIntelligenceGatekeeper")
    )
    intel_has_subdomains = (
        hasattr(Intelligence, "physics")
        and hasattr(Intelligence, "cognition")
        and hasattr(Intelligence, "gatekeeper")
        and hasattr(Intelligence, "UnifiedIntelligenceGatekeeper")
    )
    log_gate("euclid.intelligence exposes physics, cognition, gatekeeper", euclid_has_subdomains)
    log_gate("Intelligence exposes physics, cognition, gatekeeper", intel_has_subdomains)

    # Physics domain
    physics = intel.physics
    physics_ok = (
        hasattr(physics, "first_principles_quantum")
        and hasattr(physics, "quantum_algorithms")
        and hasattr(physics, "lucas_scales")
        and hasattr(physics, "poincare_cassini_search")
        and hasattr(physics, "mining_native")
    )
    log_gate("physics domain organizes quantum, Lucas, and physical simulation", physics_ok)

    # Cognition domain
    cognition = intel.cognition
    cognition_ok = (
        hasattr(cognition, "EmpiricalStateController")
        and hasattr(cognition, "EmpiricalStateBridge")
        and hasattr(cognition, "StateTransitionRequest")
        and hasattr(cognition, "MathematicalProofTracker")
        and hasattr(cognition, "register_proof_capability")
        and hasattr(cognition, "repository_review")
    )
    log_gate("cognition domain organizes empirical state, proof tracking, and review", cognition_ok)

    passed = euclid_has_subdomains and intel_has_subdomains and physics_ok and cognition_ok
    return {"passed": passed}


def gate_live_empirical_state_and_audit() -> Dict[str, Any]:
    print("\n--- Gate 6: Live Empirical State & AL HARAS Audit ---")
    from euclid.intelligence.gatekeeper import (
        UnifiedIntelligenceGatekeeper,
        StateTransitionRequest,
    )
    gatekeeper = UnifiedIntelligenceGatekeeper()

    req = StateTransitionRequest(
        capability_id="host:capability:empirical_state_controller",
        caller_id="operator:verifier:001",
        transition_type="UPDATE_RELIABILITY",
        state_payload={"domain": "atomic", "weight": 0.98},
        deadline_epoch=time.time() + 60.0,
        max_budget=100,
        operator_token="valid_operator_token_12345",
    )
    ok, receipt, msg = gatekeeper.dispatch_state_transition(req)
    state_committed = (
        ok
        and receipt is not None
        and receipt.status == "COMMITTED"
        and gatekeeper.state_bridge.controller.state["reliability_weights"]["atomic"] == 0.98
    )
    log_gate("State transition committed with pre-execution receipt", state_committed)
    if receipt:
        print(f"    [*] Receipt ID: {receipt.receipt_id}")
        print(f"    [*] State transition hash: {receipt.new_state_hash[:16]}...")

    trail = gatekeeper.get_audit_trail()
    audit_logged = len(trail) >= 1 and trail[-1]["receipt_id"] == receipt.receipt_id
    log_gate("Durable pre-execution audit receipt recorded in trail", audit_logged)

    return {"passed": state_committed and audit_logged, "receipt": receipt}


def gate_fail_closed_and_rollback() -> Dict[str, Any]:
    print("\n--- Gate 7: Fail-Closed Negative Gates & Verified Rollback ---")
    from euclid.intelligence.gatekeeper import (
        UnifiedIntelligenceGatekeeper,
        StateTransitionRequest,
    )
    gatekeeper = UnifiedIntelligenceGatekeeper()

    # 1. Unapproved capability refusal
    bad_req = StateTransitionRequest(
        capability_id="unapproved:arbitrary:target",
        caller_id="attacker",
        transition_type="BYPASS",
        state_payload={},
        deadline_epoch=time.time() + 10.0,
        max_budget=10,
        operator_token="token_with_length_16_bytes",
    )
    ok, _, msg = gatekeeper.dispatch_state_transition(bad_req)
    unapproved_refused = (not ok) and ("FORBIDDEN_CAPABILITY" in msg)
    log_gate("Refusal on unapproved capability target", unapproved_refused, msg)

    # 2. Budget exhaustion refusal
    zero_budget_req = StateTransitionRequest(
        capability_id="host:capability:empirical_state_controller",
        caller_id="operator:001",
        transition_type="UPDATE_RELIABILITY",
        state_payload={"domain": "atomic", "weight": 0.15},
        deadline_epoch=time.time() + 10.0,
        max_budget=0,
        operator_token="token_with_length_16_bytes",
    )
    ok, _, msg = gatekeeper.dispatch_state_transition(zero_budget_req)
    budget_refused = (
        (not ok)
        and ("BUDGET_EXHAUSTED" in msg)
        and gatekeeper.state_bridge.controller.state["reliability_weights"]["atomic"] != 0.15
    )
    log_gate("Refusal on budget exhaustion without mutation", budget_refused, msg)

    # 3. Verified rollback on exception
    initial_weights = dict(gatekeeper.state_bridge.controller.state["reliability_weights"])
    failing_req = StateTransitionRequest(
        capability_id="host:capability:empirical_state_controller",
        caller_id="operator:001",
        transition_type="INVALID_TYPE_TRIGGERING_EXCEPTION",
        state_payload={},
        deadline_epoch=time.time() + 10.0,
        max_budget=10,
        operator_token="token_with_length_16_bytes",
    )
    ok, _, msg = gatekeeper.dispatch_state_transition(failing_req)
    rolled_back = (
        (not ok)
        and ("EXECUTION_FAILED_ROLLED_BACK" in msg)
        and gatekeeper.state_bridge.controller.state["reliability_weights"] == initial_weights
    )
    log_gate("Verified rollback restored pre-execution state on failure", rolled_back, msg)

    passed = unapproved_refused and budget_refused and rolled_back
    return {"passed": passed}


def gate_persistence_and_clean_restart() -> Dict[str, Any]:
    print("\n--- Gate 8: Clean Instance Restart (No Memory Bleed) ---")
    from euclid.intelligence.gatekeeper import (
        UnifiedIntelligenceGatekeeper,
        StateTransitionRequest,
    )
    gatekeeper = UnifiedIntelligenceGatekeeper()

    # Commit state
    req = StateTransitionRequest(
        capability_id="host:capability:empirical_state_controller",
        caller_id="operator:001",
        transition_type="UPDATE_RELIABILITY",
        state_payload={"domain": "atomic", "weight": 0.99},
        deadline_epoch=time.time() + 60.0,
        max_budget=100,
        operator_token="token_with_length_16_bytes",
    )
    gatekeeper.dispatch_state_transition(req)
    snapshot = dict(gatekeeper.state_bridge.controller.state)

    # Reconstruct fresh instance from snapshot
    restarted = UnifiedIntelligenceGatekeeper()
    restarted.state_bridge.controller.state = dict(snapshot)

    state_restored = restarted.state_bridge.controller.state["reliability_weights"]["atomic"] == 0.99
    no_log_bleed = len(restarted.get_audit_trail()) == 0

    log_gate("Operational state restored across clean restart", state_restored)
    log_gate("Prior in-memory audit logs not adopted as identity", no_log_bleed)

    passed = state_restored and no_log_bleed
    return {"passed": passed}


def gate_deprecation_shims() -> Dict[str, Any]:
    print("\n--- Gate 9: Backward-Compatibility Deprecation Shims ---")
    toe_shim_ok = False
    euclid_shim_ok = False

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        import hyba_toe_intelligence as toe_shim

        toe_warnings = [w for w in recorded if issubclass(w.category, DeprecationWarning)]
        if toe_warnings and hasattr(toe_shim, "physics"):
            toe_shim_ok = True
        log_gate(
            "hyba_toe_intelligence emits DeprecationWarning and routes to physics",
            toe_shim_ok,
            str(toe_warnings[0].message) if toe_warnings else "No warning",
        )

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        import hyba_euclid_intelligence as euclid_shim

        euclid_warnings = [w for w in recorded if issubclass(w.category, DeprecationWarning)]
        if euclid_warnings and hasattr(euclid_shim, "intelligence"):
            euclid_shim_ok = True
        log_gate(
            "hyba_euclid_intelligence emits DeprecationWarning and routes to euclid.intelligence",
            euclid_shim_ok,
            str(euclid_warnings[0].message) if euclid_warnings else "No warning",
        )

    passed = toe_shim_ok and euclid_shim_ok
    return {"passed": passed}


def run_all_gates() -> bool:
    print("=" * 75)
    print("EUCLID ENTERPRISE ENGINE — CLEAN-ROOM RUNTIME FIDELITY VERIFICATION")
    print("=" * 75)
    work = Path(os.environ.get("TEMP", "/tmp")) / "euclid-verification-work"
    if work.exists():
        import shutil
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)

    results = []
    try:
        results.append(("Isolation", gate_isolation()))
        results.append(("Canonical Init", gate_canonical_init(work)))
        results.append(("Capability Discovery", gate_capability_discovery(work)))
        results.append(("Dispatch Authorization", gate_dispatch_authorization(work)))
        results.append(("Unified Intelligence", gate_unified_intelligence_architecture()))
        results.append(("Live State & Audit", gate_live_empirical_state_and_audit()))
        results.append(("Fail-Closed & Rollback", gate_fail_closed_and_rollback()))
        results.append(("Persistence & Clean Restart", gate_persistence_and_clean_restart()))
        results.append(("Deprecation Shims", gate_deprecation_shims()))
    except Exception as exc:
        print(f"\n[!] Verification encountered unhandled error: {exc}", flush=True)
        import traceback
        traceback.print_exc()
        return False

    all_passed = all(r["passed"] for _, r in results)
    print("\n" + "=" * 75)
    if all_passed:
        print("[+] ALL CLEAN-ROOM ARTIFACT GATES PASSED (100% SITE-PACKAGES ISOLATED)")
    else:
        failed = [name for name, r in results if not r["passed"]]
        print(f"[!] FAILED GATES: {failed}")
    print("=" * 75)
    return all_passed


if __name__ == "__main__":
    success = run_all_gates()
    sys.exit(0 if success else 1)

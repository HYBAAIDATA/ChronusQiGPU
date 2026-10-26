"""Installed-artifact acceptance. Invoke through run_clean_install.py.

All checks use unconditional branches (also under -O). Random local test keys
exercise real contracts, not independent assurance or production authorization.
No provider, mining pool, deployment, repair, or network operation is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import importlib.resources
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import tempfile
import time


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def verify_installed_members(manifest, expected_commit):
    """Check installed bytes against this invocation's owner wheel manifests.

    This is local reproducibility evidence, not a signature or release approval.
    pip rewrites RECORD during installation; all other original wheel members
    are checked, including package data, METADATA and embedded provenance.
    """
    require(manifest.get("source_commit") == expected_commit, "manifest commit mismatch")
    owners = manifest.get("owned_distributions", {})
    require(
        set(owners) == {"euclid-engine", "hyba-turing-vqc", "hyba-kellogg-tensor"},
        "canonical owner artifacts missing",
    )
    checked = {}
    for name, item in owners.items():
        distribution = importlib.metadata.distribution(name)
        require(distribution.version == "1.0.0", f"unexpected owner version: {name}")
        require(bool(item["members"]), f"empty artifact manifest: {name}")
        for member, digest in item["members"].items():
            relative = Path(member)
            require(
                not relative.is_absolute() and ".." not in relative.parts,
                "unsafe artifact member path",
            )
            if member.endswith("/") or member.endswith(".dist-info/RECORD"):
                continue
            installed = Path(distribution.locate_file(member))
            require(
                installed.is_file()
                and hashlib.sha256(installed.read_bytes()).hexdigest() == digest,
                f"installed artifact member mismatch: {name}:{member}",
            )
        checked[name] = {"wheel": item["wheel"], "version": distribution.version}
    return checked


def isolation(repo, expected_commit):
    require(sys.prefix != sys.base_prefix, "acceptance requires a fresh virtual environment")
    roots = {Path(sysconfig.get_path(name)).resolve() for name in ("purelib", "platlib")}
    for root in roots:
        require(root.is_relative_to(Path(sys.prefix).resolve()), "site-packages outside venv")
    require(not Path.cwd().resolve().is_relative_to(repo), "cwd is inside checkout")
    for entry in sys.path:
        require(
            not Path(entry or os.getcwd()).resolve().is_relative_to(repo),
            "checkout present on sys.path",
        )
    names = (
        "euclid",
        "Intelligence",
        "aethel",
        "al_haras",
        "kellogg",
        "toe",
        "lucas",
        "turing_universal_quantum_computer",
    )
    paths = {}
    for name in names:
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve()
        require(any(path.is_relative_to(root) for root in roots), f"non-installed import: {name}")
        paths[name] = str(path)
    # Also catches checkout imports reached lazily during real dispatch.
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if filename:
            require(not Path(filename).resolve().is_relative_to(repo), "lazy checkout import")
    require(importlib.metadata.version("euclid-engine") == "1.0.0", "wrong distribution version")
    try:
        importlib.metadata.version("hyba-pythia-mining")
    except importlib.metadata.PackageNotFoundError:
        pass
    else:
        raise RuntimeError("mining umbrella must not satisfy enterprise acceptance")
    provenance = json.loads(
        importlib.resources.files("euclid").joinpath("_artifact_provenance.json").read_text()
    )
    require(provenance["source_commit"] == expected_commit, "artifact commit mismatch")
    return paths


def lifecycle_for(work):
    from aethel.enterprise.lifecycle import CompositionRoot

    return CompositionRoot(
        work / "custody", tenant="clean-room", hmac_key=(work / "custody.key").read_bytes()
    )


def state_from_port(port):
    from euclid.capabilities.empirical_state_bridge import EmpiricalStateBridge

    binding = port.latest(EmpiricalStateBridge.STATE_KIND)
    require(binding is not None, "operational state not persisted")
    return json.loads(port.read(binding.binding_id))


def recover_actual_publication(port, audit):
    """Inject a post-publication response loss over the actual shared port."""
    from euclid.capabilities.empirical_state_bridge import (
        EmpiricalStateBridge,
        StateTransitionRequest,
        StateCommitUncertain,
    )
    from euclid.capabilities.empirical_recovery import (
        PublicationRecoveryRequest,
        reconcile_publication,
    )
    import secrets

    secret = secrets.token_urlsafe(32)

    class ResponseLossPort:
        # Delegate to actual custody. Only the response loss is a fault fixture.
        latest = port.latest
        read = port.read

        def put(self, *args, **kwargs):
            port.put(*args, **kwargs)
            raise OSError("acceptance fixture: response lost after real publication")

    bridge = EmpiricalStateBridge(
        audit=audit,
        data_port=ResponseLossPort(),
        owner_id="clean-room-owner",
        authorizer=lambda req: req.caller_id == "fixture-writer"
        and secrets.compare_digest(req.operator_token, secret),
    )
    try:
        bridge.dispatch(
            StateTransitionRequest(
                bridge.APPROVED_CAPABILITY_ID,
                "fixture-writer",
                "UPDATE_RELIABILITY",
                {"domain": "atomic", "weight": 0.99},
                time.time() + 60,
                1,
                secret,
            )
        )
    except StateCommitUncertain:
        pass
    else:
        raise RuntimeError("uncertain actual publication reported success")
    binding = port.latest(bridge.STATE_KIND)
    request = PublicationRecoveryRequest(
        "clean-room-owner",
        binding.binding_id,
        hashlib.sha256(port.read(binding.binding_id)).hexdigest(),
        "fixture-recovery",
        secret,
        time.time() + 60,
    )
    try:
        reconcile_publication(request, audit=audit, data_port=port)
    except PermissionError:
        pass
    else:
        raise RuntimeError("recovery without independent authority accepted")
    receipt = reconcile_publication(
        request,
        audit=audit,
        data_port=port,
        recovery_authorizer=lambda req: req.caller_id == "fixture-recovery"
        and secrets.compare_digest(req.operator_token, secret),
    )
    restored = EmpiricalStateBridge(
        audit=audit,
        data_port=port,
        owner_id="clean-room-owner",
    )
    require(restored.audit_log[-1] == receipt, "actual publication recovery missing completion")
    return {
        "receipt_id": receipt.receipt_id,
        "custody_binding_id": binding.binding_id,
        "fault": "response loss after actual shared-port publication",
        "authority": "ephemeral explicit host-policy fixture, not enterprise approval",
    }


def reader(work):
    from al_haras import HashChainAudit
    from aethel.enterprise.system_relations import SharedTuring
    from euclid.runtime import EuclidRuntime

    prior = json.loads((work / "restart.json").read_text())
    lifecycle = lifecycle_for(work)
    lifecycle.start()
    try:
        with_runtime = EuclidRuntime(creator_id="clean-room-owner", state_dir=work / "runtime")
        try:
            port = lifecycle.data_port("euclid")
            with_runtime.bind_adaptive_data_port(port)
            with_runtime.compose_adaptive_intelligence()
            verified = with_runtime.verify_adaptive_restart_receipt(prior["adaptive"])
            require(verified["passed"], "adaptive restart verification failed")
            require(
                not with_runtime.rights.snapshot()["grants"], "restart adopted dispatch authority"
            )
            with_runtime.bind_empirical_state(data_port=port)
            envelope = state_from_port(port)
            require(envelope == prior["operational"], "operational state changed across restart")
            audit = HashChainAudit(work / "runtime/empirical/empirical-state.jsonl")
            require(audit.verify(audit.records), "audit chain failed after restart")
            require(
                any(r["event"].get("receipt") == envelope["receipt"] for r in audit.records),
                "durable operational receipt missing",
            )
            require(os.getpid() != prior["pid"], "restart did not cross process boundary")
            turing_replay = SharedTuring(lifecycle.data_port("turing")).replay()
            require(
                turing_replay["passed"]
                and turing_replay["replay_source"] == "durable_graph"
                and turing_replay["report_binding_id"] == prior["turing_report_binding_id"],
                "native TURING shared-custody restart failed",
            )
            return {
                "pid": os.getpid(),
                "adaptive": verified,
                "operational": "RESTORED",
                "authority": "FRESH_NO_GRANTS",
                "audit": "RESTORED_AND_VERIFIED",
                "turing": turing_replay,
            }
        finally:
            with_runtime.close()
    finally:
        lifecycle.stop()


def writer(work, args):
    from al_haras import (
        ALHaras,
        GuardianPolicy,
        HashChainAudit,
        SubscriptionAuthority,
        SubscriptionClaims,
    )
    from Intelligence.capability_fabric import CapabilityRegistry, ExecutionProfile
    from Intelligence.mathematical_research import MathematicalProofTracker
    from Intelligence.proof_capability import register_proof_capability
    from Intelligence.repository_review import ReviewPolicy
    from Intelligence.repository_review_capability import register_repository_review_capability
    from euclid.cognition.worlds import MechanismWorld, WorldExecutor, generate_task
    from euclid.runtime import EuclidRuntime
    from euclid.contracts import Authority
    from euclid.organ_adapters.specialists import TuringQuantumOrgan
    from aethel.enterprise.system_relations import SharedTuring
    from turing_universal_quantum_computer.backends import Program

    lifecycle = lifecycle_for(work)
    lifecycle.start()
    runtime = None
    try:
        runtime = EuclidRuntime(creator_id="clean-room-owner", state_dir=work / "runtime")
        require(runtime.startup_report()["schema"] == "euclid.startup/1", "startup schema")
        require(not runtime.rights.snapshot()["grants"], "unearned initial grants")
        port = lifecycle.data_port("euclid")
        runtime.bind_adaptive_data_port(port)
        runtime.compose_adaptive_intelligence()
        registry = CapabilityRegistry()
        register_proof_capability(registry, MathematicalProofTracker())
        approved = work / "review"
        approved.mkdir()
        source = approved / "example.py"
        source.write_text("value = 3\n")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        register_repository_review_capability(
            registry,
            repo_root=approved,
            approved_policies={"fixture": ReviewPolicy((("example.py", digest),))},
        )
        specialist = runtime.bind_intelligence(
            registry,
            profile=ExecutionProfile.INTERNAL_RESEARCH,
            capabilities=["proof-conjecture", "repository-review"],
        )
        empirical = runtime.bind_empirical_state(data_port=port)
        shared_turing = SharedTuring(lifecycle.data_port("turing"))
        runtime.register_specialist(
            "turing",
            TuringQuantumOrgan(pipeline=shared_turing),
            operations=("run-program",),
            authority=Authority.PROPOSE,
        )
        catalog = specialist.catalog() + empirical.catalog()
        require(
            {r["capability_id"] for r in catalog}
            == {
                "proof-conjecture",
                "repository-review",
                "host:capability:empirical_state_controller",
            },
            "native capability discovery incomplete",
        )
        profiles = [profile.value for profile in ExecutionProfile]
        require(profiles == ["internal", "shared"], "execution profile contract changed")

        authority = SubscriptionAuthority({"fixture": os.urandom(32)}, "clean-room-authority")
        audit = HashChainAudit(work / "guardian/decisions.jsonl")
        runtime.guardian = ALHaras(
            authority,
            GuardianPolicy(
                "clean-room-policy",
                allowed_operations=frozenset(
                    {
                        "intelligence.proof-conjecture",
                        "intelligence.repository-review",
                        "empirical-state.UPDATE_RELIABILITY",
                        "empirical-state.INVALID_TRANSITION",
                        "turing.run-program",
                    }
                ),
            ),
            audit,
        )
        now = int(time.time())
        token = authority.issue(
            SubscriptionClaims(
                "fixture-subscription",
                "clean-room",
                "clean-room-authority",
                "fixture",
                ("hyba.security",),
                ("verifier",),
                now - 1,
                now + 300,
            )
        )

        def dispatch(organ, operation, arguments, credential=token):
            return runtime.dispatch_specialist(
                organ,
                {"operation": operation, "arguments": arguments},
                tenant_id="clean-room",
                actor="verifier",
                subscription_token=credential,
            )

        proof = {
            "action": "register",
            "conjecture_id": "clean-room-c",
            "domain": "test",
            "statement": "Acceptance fixture, not a proven theorem",
        }
        require(
            not dispatch("intelligence", "proof-conjecture", proof)["allowed"],
            "missing creator rights not refused",
        )
        for organ in ("intelligence", "empirical-state", "turing"):
            runtime.rights.grant(runtime.creator_id, organ, organ + ".request", "dispatch")
        for credential in ("", "arbitrary-not-a-credential"):
            require(
                not dispatch("intelligence", "proof-conjecture", proof, credential)["allowed"],
                "invalid entitlement accepted",
            )
        result = dispatch("intelligence", "proof-conjecture", proof)
        require(result["allowed"] and result["result"]["executed"], "native conjecture failed")
        result = dispatch("intelligence", "repository-review", {"review_id": "fixture"})
        require(
            result["allowed"]
            and result["result"]["executed"]
            and result["result"]["output"]["files"][0]["sha256"] == digest,
            "native source-bound review failed",
        )
        # Exercise the actual canonical installed pipeline through EUCLID and
        # its existing SharedTuring custody adapter, not an injected stand-in.
        program = Program(1).then("H", 0).then("H", 0)
        turing_request = {"operation": "run-program", "program": program.to_dict()}
        for credential in ("", "x" * 100, token):
            turing_result = runtime.dispatch_specialist(
                "turing",
                turing_request,
                tenant_id="clean-room",
                actor="verifier",
                subscription_token=credential,
            )
            if credential != token:
                require(not turing_result["allowed"], "invalid TURING authority accepted")
            else:
                require(
                    turing_result["allowed"]
                    and turing_result["result"]["executed"]
                    and turing_result["result"]["pipeline_verdict"] == "PASS",
                    "canonical installed TURING dispatch failed",
                )
        turing_replay = shared_turing.replay()
        require(turing_replay["passed"], "native TURING custody replay failed")
        request = {
            "state_payload": {"domain": "atomic", "weight": 0.99},
            "deadline_epoch": time.time() + 60,
            "max_budget": 1,
        }
        result = dispatch("empirical-state", "UPDATE_RELIABILITY", request)
        require(
            result["allowed"] and result["result"]["executed"], "native empirical dispatch failed"
        )
        before = state_from_port(port)
        for arguments, reason in (
            ({**request, "max_budget": 0}, "BUDGET_EXHAUSTED"),
            ({**request, "deadline_epoch": time.time() - 1}, "DEADLINE_EXPIRED"),
        ):
            result = dispatch("empirical-state", "UPDATE_RELIABILITY", arguments)
            require(
                not result["result"]["executed"] and result["result"]["status"] == reason,
                "negative transition gate failed",
            )
        result = dispatch("empirical-state", "INVALID_TRANSITION", request)
        require(
            result["result"]["status"] == "EXECUTION_FAILED_ROLLED_BACK", "rollback gate failed"
        )
        require(state_from_port(port) == before, "negative gates mutated durable state")
        require(
            not dispatch("empirical-state", "unapproved-operation", request)["allowed"],
            "unapproved operation not refused",
        )
        runtime.rights.revoke(
            runtime.creator_id, "empirical-state", "empirical-state.request", "dispatch"
        )
        require(
            not dispatch("empirical-state", "UPDATE_RELIABILITY", request)["allowed"],
            "revoked rights accepted",
        )
        spec, truth = generate_task("program-transformation", seed=37, partition="evaluation")
        runtime.solve_task(spec, WorldExecutor(MechanismWorld(spec, truth)), seed=37)
        prior = {
            "pid": os.getpid(),
            "operational": before,
            "adaptive": runtime.adaptive_restart_receipt(),
            "turing_report_binding_id": shared_turing.last_bindings["report"].binding_id,
        }
        require(not (runtime.state_dir / "adaptive_knowledge.json").exists(), "private state leak")
        (work / "restart.json").write_text(json.dumps(prior))
        state_audit = HashChainAudit(work / "runtime/empirical/empirical-state.jsonl")
        phases = [r["event"]["phase"] for r in state_audit.records]
        require(
            phases == ["ADMITTED", "PREPARED", "COMMITTED", "ADMITTED", "ROLLED_BACK"],
            "missing durable admission/completion/rollback",
        )
        require(
            token not in (work / "runtime/empirical/empirical-state.jsonl").read_text(),
            "credential leaked into empirical audit",
        )
        # Maintenance begins only after the runtime writer has been closed.
        runtime.close()
        runtime = None
        recovery = recover_actual_publication(port, state_audit)
        prior["operational"] = state_from_port(port)
        (work / "restart.json").write_text(json.dumps(prior))
    finally:
        if runtime is not None:
            runtime.close()
        lifecycle.stop()
    command = [sys.executable, "-I"]
    if sys.flags.optimize:
        command += ["-O"]
    # run_path executes only the copied verifier; cwd stays empty and sys.path isolated.
    command += [
        "-c",
        "import runpy,sys; p=sys.argv.pop(1); runpy.run_path(p,run_name='__main__')",
        str(Path(__file__).resolve()),
        "--reader",
        "--work",
        str(work),
        "--repo-root",
        str(args.repo_root),
        "--expected-commit",
        args.expected_commit,
        "--build-manifest",
        str(args.build_manifest),
    ]
    completed = subprocess.run(command, check=True, text=True, capture_output=True, timeout=300)
    restart = json.loads(completed.stdout.strip().splitlines()[-1])
    return {
        "catalog": catalog,
        "profiles": profiles,
        "restart": restart,
        "native_paths": ["proof-conjecture", "repository-review", "empirical-state", "turing"],
        "turing": turing_replay,
        "recovery": recovery,
        "limits": "bounded in-process tests; not independent assurance or production qualification",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--reader", action="store_true")
    parser.add_argument("--work", type=Path)
    parser.add_argument("--build-manifest", type=Path, required=True)
    args = parser.parse_args()
    args.repo_root = args.repo_root.resolve()
    args.build_manifest = args.build_manifest.resolve()
    manifest = json.loads(args.build_manifest.read_text())
    owners = verify_installed_members(manifest, args.expected_commit)
    paths = isolation(args.repo_root, args.expected_commit)
    if args.reader:
        result = reader(args.work)
    else:
        with tempfile.TemporaryDirectory(prefix="euclid-acceptance-") as tmp:
            work = Path(tmp)
            require(not work.resolve().is_relative_to(args.repo_root), "work is inside checkout")
            (work / "custody.key").write_bytes(os.urandom(32))
            (work / "custody.key").chmod(0o600)
            result = writer(work, args)
    isolation(args.repo_root, args.expected_commit)
    verify_installed_members(manifest, args.expected_commit)
    print(
        json.dumps(
            {
                "passed": True,
                "optimized": bool(sys.flags.optimize),
                "imports": paths,
                "artifacts": owners,
                **result,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

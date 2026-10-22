"""Deployment entry points. Secrets are files, never command-line values."""

import argparse
import base64
import json
import os
from pathlib import Path
import signal
import sqlite3
import stat
import time

from .api import Dependencies, create_app
from .enterprise import EnterprisePlane
from .identity import OIDCVerifier
from .sessions import Sessions
from .commercial import validate_scope
from .release import verify_bundle
from .runtime import ProcessRuntime, ResultCustody
from .supervisor import Supervisor


def read_secret(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
            raise ValueError("secret file must be regular and private (0600)")
        data = os.read(fd, 65537)
        if len(data) > 65536:
            raise ValueError("secret file too large")
        return data.decode().strip()
    finally:
        os.close(fd)


def configuration(path):
    os.umask(0o077)
    config = json.loads(Path(path).read_text())
    validate_scope(config)
    from al_haras.entitlements import SubscriptionAuthority, SubscriptionClaims

    if set(config["operator_subjects"]) & set(config["approver_subjects"]):
        raise ValueError("operator and commercial approver identities must be distinct")
    if read_secret(config["customer_key_file"]) == read_secret(config["operator_key_file"]):
        raise ValueError("customer and operator signing keys must be distinct")
    customer = SubscriptionAuthority(
        {
            config["key_id"]: base64.b64decode(
                read_secret(config["customer_key_file"]), validate=True
            )
        },
        config["customer_issuer"],
    )
    operator = SubscriptionAuthority(
        {
            config["key_id"]: base64.b64decode(
                read_secret(config["operator_key_file"]), validate=True
            )
        },
        config["operator_issuer"],
    )

    def factory():
        return EnterprisePlane(
            config["database"],
            customer_authority=customer,
            operator_authority=operator,
            capacity_slots=config["capacity_slots"],
            require_spend=False,
        )

    plane = factory()
    plane.close()

    def machine_token(capabilities):
        now = int(time.time())
        return operator.issue(
            SubscriptionClaims(
                subscription_id="turing-service-worker",
                tenant_id="__service_ops__",
                issuer=operator.issuer,
                key_id=config["key_id"],
                capabilities=tuple(capabilities),
                actors=(config["worker_subject"],),
                not_before=now - 1,
                expires_at=now + 60,
            )
        )

    billing = None  # No approved current-release financial service.
    return config, customer, operator, SubscriptionClaims, factory, machine_token, billing


def main():
    parser = argparse.ArgumentParser(description="TURING enterprise service operations")
    parser.add_argument(
        "command", choices=["serve", "worker", "billing", "backup", "restore", "release-check"]
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--destination")
    parser.add_argument("--publication", action="store_true")
    args = parser.parse_args()
    config, customer, operator, Claims, factory, machine_token, billing = configuration(args.config)
    if args.command == "billing":
        raise ValueError("billing is deferred; no provider is authorised")
    if args.command == "restore":
        if not args.destination or Path(args.destination).exists():
            raise ValueError("restore requires a new destination")
        source = sqlite3.connect("file:" + config["backup_source"] + "?mode=ro", uri=True)
        target = sqlite3.connect(args.destination)
        try:
            if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("backup integrity failure")
            source.backup(target)
        finally:
            source.close()
            target.close()
        return
    if args.command == "backup":
        plane = factory()
        try:
            if args.command == "backup":
                if not args.destination or Path(args.destination).exists():
                    raise ValueError("new backup destination required")
                plane.backup(
                    machine_token(["turing.ops.manage"]), config["worker_subject"], args.destination
                )
                os.chmod(args.destination, 0o600)
        finally:
            plane.close()
        return

    def approval():
        # Build identity is baked into the read-only image, not supplied by HTTP.
        built_commit = (
            Path(config.get("build_identity_file", "/opt/service-source-commit"))
            .read_text()
            .strip()
        )
        if built_commit != config["source_commit"] or len(built_commit) != 40:
            raise ValueError("running image source does not match approved commit")
        verify_bundle(
            config["approval_bundle"],
            config["approval_public_key"],
            config["source_commit"],
            publication=args.publication,
        )
        return True

    if args.command == "release-check":
        approval()
        return
    if config.get("mode") != "controlled-pilot":
        approval()
    if args.command == "worker":
        supervisor = Supervisor(
            factory,
            lambda: machine_token(["turing.ops.execute"]),
            config["worker_subject"],
            config["custody_root"],
        )
        signal.signal(signal.SIGTERM, lambda *_: setattr(supervisor, "stopping", True))
        signal.signal(signal.SIGINT, lambda *_: setattr(supervisor, "stopping", True))
        supervisor.run()
        return
    verifier = OIDCVerifier(config["oidc_issuer"], config["api_audience"], config["jwks_url"])
    session_verifier = OIDCVerifier(config["oidc_issuer"], config["client_id"], config["jwks_url"])
    sessions = Sessions(
        config["database"],
        origin=config["origin"],
        issuer=config["oidc_issuer"],
        client_id=config["client_id"],
        redirect_uri=config["origin"] + "/auth/callback",
        authorization_url=config["authorization_url"],
        token_url=config["token_url"],
        verifier=session_verifier,
        encryption_key=read_secret(config["session_key_file"]).encode(),
        client_secret=(
            read_secret(config["oidc_client_secret_file"])
            if config.get("oidc_client_secret_file")
            else None
        ),
    )
    ready_cache = [0, False]

    def ready():
        if time.monotonic() - ready_cache[0] < 30:
            return ready_cache[1]
        try:
            if config.get("mode") != "controlled-pilot":
                approval()
            report = ProcessRuntime(timeout=20).run(
                {"qasm": "OPENQASM 2.0; qreg q[1]; h q[0];", "shots": 8, "seed": 1}
            )
            good = report.get("verdict") == "PASS" and bool(report.get("certificate"))
        except Exception:
            good = False
        ready_cache[:] = [time.monotonic(), good]
        return good

    app = create_app(
        Dependencies(
            factory,
            verifier,
            customer,
            operator,
            Claims,
            config["key_id"],
            frozenset(config["operator_subjects"]),
            frozenset(config["approver_subjects"]),
            config["origin"],
            sessions,
            billing,
            ready,
            False,  # Contract, membership and capacity checks remain mandatory.
            ResultCustody(config["custody_root"]),
        )
    )
    import uvicorn

    uvicorn.run(
        app,
        host=config.get("bind", "127.0.0.1"),
        port=config.get("port", 8080),
        proxy_headers=False,
        server_header=False,
    )


if __name__ == "__main__":
    main()

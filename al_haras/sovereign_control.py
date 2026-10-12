"""AL HARAS sovereign control plane: runtime egress, ingestion and storage boundary.

``hyba_profiles`` and ``chronus.mla1517.deployment`` *declare* an
``air_gapped`` deployment; this module *enforces* it inside every Python
process of a sovereign deployment and records what it refused.

Modes (``HYBA_SOVEREIGN_MODE``):

``connected``   default. Nothing is installed; behaviour is unchanged.
``private``     outbound connections only to loopback, Unix sockets and
                explicitly allowlisted networks/hosts (any address class).
``air_gapped``  as ``private``, but every allowlisted network must be
                non-global (RFC 1918, ULA, link-local); a public allowlist
                entry is a configuration error and the process refuses to
                start.

Enforcement is a CPython audit hook (PEP 578) on ``socket.connect``,
``socket.sendto``, ``socket.sendmsg``, ``socket.getaddrinfo``,
``socket.gethostbyname`` and ``socket.gethostbyaddr``. Audit hooks cannot be
removed once added, and raising from one aborts the operation before the
kernel sees it, so every library in the process (urllib, requests, aiohttp,
asyncio, boto3, azure-storage, ...) is covered without being modified.
Denials raise :class:`SovereignEgressDenied`, a ``PermissionError`` -- the
same family a firewall refusal produces -- so callers fail closed through
their normal error paths.

Every denial (coalesced per target), the first use of each permitted
target, every subprocess spawn, every ingestion/storage decision and every
attestation is appended to an AL HARAS :class:`~al_haras.audit.HashChainAudit`
(``HYBA_SOVEREIGN_AUDIT_PATH``). The chain is tamper-evident; anchoring its
head hash in an HMAC-signed attestation (``HYBA_SOVEREIGN_ATTESTATION_KEY``)
means an operator without the key cannot rewrite the whole chain either.

Truth boundary: an in-process hook is defence in depth. It cannot police
native code that bypasses CPython's socket module, or non-Python child
processes. The deployment boundary is the container network (an
``internal: true`` Docker network, see ``docker-compose.sovereign.yml``);
the proof pack probes that boundary separately and reports it, rather than
inferring it from this hook.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import ipaddress
import json
import os
import platform
import socket
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional
from urllib.parse import urlsplit

from .audit import HashChainAudit, canonical_json, digest

SCHEMA_ATTESTATION = "hyba.sovereign-attestation/1"
SCHEMA_EVENT = "hyba.sovereign-event/1"
MODES = ("connected", "private", "air_gapped")
ENV_MODE = "HYBA_SOVEREIGN_MODE"
ENV_EGRESS = "HYBA_SOVEREIGN_EGRESS_ALLOW"
ENV_AUDIT = "HYBA_SOVEREIGN_AUDIT_PATH"
ENV_KEY = "HYBA_SOVEREIGN_ATTESTATION_KEY"
ENV_STORAGE_ROOTS = "HYBA_SOVEREIGN_STORAGE_ROOTS"
ENV_ISOLATION = "HYBA_SOVEREIGN_NETWORK_ISOLATION"
ENV_ROLE = "HYBA_SOVEREIGN_ROLE"
ENV_BUILD = "HYBA_BUILD_COMMIT"
MIN_KEY_BYTES = 32
# Storage-location variables of the sovereign products: each must name a
# local path in private/air-gapped mode (checked at install).
STORAGE_ENV = (
    "PYTHIA_STORAGE_DB",
    "PYTHIA_STORAGE_ROOT",
    "PYTHIA_STORAGE_CUSTODY_ROOT",
    "AL_HARAS_DATA_DIR",
    "PYTHIA_STORE_DIR",
    "THESEUS_ROOT",
    "OVID_DB_PATH",
)
REMOTE_SCHEMES = frozenset(
    {
        "http", "https", "ftp", "ftps", "sftp", "ssh", "s3", "s3a", "gs", "gcs",
        "az", "azure", "abfs", "abfss", "wasb", "wasbs", "adl", "hdfs", "webhdfs",
        "swift", "oss", "cos", "r2", "minio", "grpc", "grpcs", "ws", "wss",
        "postgres", "postgresql", "mysql", "mongodb", "redis", "amqp", "kafka",
    }
)
_COALESCE_FIRST = 3  # denials per target always recorded; then powers of two


class SovereignConfigError(RuntimeError):
    """The sovereign configuration is invalid; the process must not start."""


class SovereignEgressDenied(PermissionError):
    """An outbound network operation was refused by the sovereign boundary."""


class SovereignBoundaryDenied(PermissionError):
    """An ingestion source or storage location was refused (not local/allowed)."""


@dataclass(frozen=True)
class EgressRule:
    network: ipaddress.IPv4Network | ipaddress.IPv6Network
    port: Optional[int]
    source: str

    def matches(self, ip: ipaddress.IPv4Address | ipaddress.IPv6Address, port: Optional[int]) -> bool:
        if ip.version != self.network.version or ip not in self.network:
            return False
        return self.port is None or port == self.port

    def as_text(self) -> str:
        return f"{self.network}" + (f":{self.port}" if self.port is not None else "")


@dataclass(frozen=True)
class SovereignPolicy:
    mode: str
    rules: tuple[EgressRule, ...] = ()
    pinned_names: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    storage_roots: tuple[Path, ...] = ()
    audit_path: Optional[Path] = None
    attestation_key: bytes = b""
    network_isolation: str = "undeclared"

    @property
    def enforcing(self) -> bool:
        return self.mode != "connected"

    def as_public_dict(self) -> dict[str, Any]:
        """The policy as attested: no key material."""
        return {
            "mode": self.mode,
            "egress_allow": sorted(rule.as_text() for rule in self.rules),
            "pinned_names": {k: list(v) for k, v in sorted(self.pinned_names.items())},
            "storage_roots": [str(p) for p in self.storage_roots],
            "network_isolation_declared": self.network_isolation,
        }

    @property
    def digest(self) -> str:
        return digest(self.as_public_dict())

    @property
    def key_id(self) -> str:
        return hashlib.sha256(self.attestation_key).hexdigest()[:16] if self.attestation_key else ""


# ---------------------------------------------------------------------------
# Policy parsing
# ---------------------------------------------------------------------------


def _split_host_port(entry: str) -> tuple[str, Optional[int]]:
    entry = entry.strip()
    if entry.startswith("["):  # [v6]:port or [v6]
        host, _, rest = entry[1:].partition("]")
        port = rest[1:] if rest.startswith(":") else ""
        return host, (int(port) if port else None)
    if entry.count(":") == 1:
        host, port = entry.split(":")
        return host, int(port)
    return entry, None


def _parse_rules(raw: str, mode: str) -> tuple[tuple[EgressRule, ...], dict[str, tuple[str, ...]]]:
    rules: list[EgressRule] = []
    pinned: dict[str, tuple[str, ...]] = {}
    for entry in (e for e in raw.replace(";", ",").split(",") if e.strip()):
        try:
            host, port = _split_host_port(entry)
        except ValueError as exc:
            raise SovereignConfigError(f"bad egress allowlist entry {entry!r}") from exc
        if port is not None and not 0 < port < 65536:
            raise SovereignConfigError(f"bad port in egress allowlist entry {entry!r}")
        try:
            networks = [ipaddress.ip_network(host, strict=False)]
        except ValueError:
            # A host name: resolve once, now, before the hook exists, and pin
            # the addresses (no later DNS can redirect an allowlisted name).
            try:
                infos = socket.getaddrinfo(host, port or 0, proto=socket.IPPROTO_TCP)
            except OSError as exc:
                raise SovereignConfigError(
                    f"allowlisted host {host!r} does not resolve at startup: {exc}"
                ) from exc
            addresses = tuple(sorted({info[4][0] for info in infos}))
            pinned[host.lower()] = addresses
            networks = [ipaddress.ip_network(a) for a in addresses]
        for network in networks:
            if mode == "air_gapped" and network.is_global:
                raise SovereignConfigError(
                    f"air_gapped mode cannot allow a global address ({entry!r} -> {network})"
                )
            rules.append(EgressRule(network, port, entry.strip()))
    return tuple(rules), pinned


def _is_remote_location(value: str) -> bool:
    scheme = urlsplit(value).scheme.lower()
    if len(scheme) == 1:  # Windows drive letter, e.g. C:\data
        return False
    return scheme in REMOTE_SCHEMES or (bool(scheme) and scheme != "file")


def load_policy(env: Optional[Mapping[str, str]] = None) -> SovereignPolicy:
    """Read and validate the sovereign policy; raise on any inconsistency."""
    env = os.environ if env is None else env
    mode = (env.get(ENV_MODE) or "connected").strip().lower().replace("-", "_")
    if mode not in MODES:
        raise SovereignConfigError(f"{ENV_MODE}={mode!r}; expected one of {', '.join(MODES)}")
    if mode == "connected":
        return SovereignPolicy(mode="connected")
    rules, pinned = _parse_rules(env.get(ENV_EGRESS, ""), mode)
    audit_raw = (env.get(ENV_AUDIT) or "").strip()
    if not audit_raw:
        raise SovereignConfigError(f"{ENV_AUDIT} is required in {mode} mode (durable audit)")
    if _is_remote_location(audit_raw):
        raise SovereignConfigError(f"{ENV_AUDIT} must be a local path, got {audit_raw!r}")
    key_raw = env.get(ENV_KEY) or ""
    try:
        key = bytes.fromhex(key_raw) if key_raw and len(key_raw) % 2 == 0 else key_raw.encode()
    except ValueError:
        key = key_raw.encode()
    if len(key) < MIN_KEY_BYTES:
        raise SovereignConfigError(
            f"{ENV_KEY} must carry at least {MIN_KEY_BYTES} bytes (e.g. openssl rand -hex 32)"
        )
    roots: list[Path] = []
    # Comma-separated: os.pathsep (':') would split URLs like gs://bucket into
    # harmless-looking fragments, and ':' appears in Windows drive paths.
    for item in (r.strip() for r in (env.get(ENV_STORAGE_ROOTS) or "").split(",") if r.strip()):
        if _is_remote_location(item):
            raise SovereignConfigError(f"storage root {item!r} is not a local path")
        roots.append(Path(item).resolve())
    policy = SovereignPolicy(
        mode=mode,
        rules=rules,
        pinned_names=pinned,
        storage_roots=tuple(roots),
        audit_path=Path(audit_raw),
        attestation_key=key,
        network_isolation=(env.get(ENV_ISOLATION) or "undeclared").strip(),
    )
    for name in STORAGE_ENV:
        value = (env.get(name) or "").strip()
        if value and _is_remote_location(value):
            raise SovereignConfigError(
                f"{name}={value!r} is a remote location; {mode} storage must be local"
            )
    return policy


# ---------------------------------------------------------------------------
# The control plane
# ---------------------------------------------------------------------------


def _ip(value: Any) -> Optional[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return ipaddress.ip_address(str(value).split("%", 1)[0])
    except ValueError:
        return None


class SovereignControlPlane:
    """Decides and records every boundary crossing for one process."""

    def __init__(self, policy: SovereignPolicy, *, role: str = "process") -> None:
        if not policy.enforcing:
            raise SovereignConfigError("connected mode installs no control plane")
        assert policy.audit_path is not None
        self.policy = policy
        self.role = role
        self.audit = HashChainAudit(policy.audit_path)
        self.installed_at = int(time.time())
        self._lock = threading.Lock()
        self._local = threading.local()
        self._denials: dict[tuple[str, str], int] = {}
        self._allowed_seen: set[tuple[str, str]] = set()
        self._hook_installed = False
        self._record("control_plane_started", policy=policy.as_public_dict(),
                     policy_digest=policy.digest, python=sys.version.split()[0])

    # -- recording ---------------------------------------------------------

    def _record(self, event: str, **detail: Any) -> dict[str, Any]:
        body = {
            "schema": SCHEMA_EVENT,
            "event": event,
            "mode": self.policy.mode,
            "role": self.role,
            "pid": os.getpid(),
            "ts": round(time.time(), 3),
            **detail,
        }
        # Recording must never re-enter the hook (it only touches files).
        self._local.busy = True
        try:
            return self.audit.append(body)
        finally:
            self._local.busy = False

    def _deny(self, kind: str, target: str, reason: str, exc: type[PermissionError]) -> None:
        with self._lock:
            count = self._denials.get((kind, target), 0) + 1
            self._denials[(kind, target)] = count
        if count <= _COALESCE_FIRST or count & (count - 1) == 0:
            self._record("denied", kind=kind, target=target, reason=reason, occurrence=count)
        raise exc(f"sovereign {self.policy.mode}: {kind} to {target} denied ({reason})")

    def _allow_first_use(self, kind: str, target: str, reason: str) -> None:
        key = (kind, target)
        with self._lock:
            if key in self._allowed_seen:
                return
            self._allowed_seen.add(key)
        self._record("allowed_first_use", kind=kind, target=target, reason=reason)

    # -- decisions ---------------------------------------------------------

    def decide_address(self, host: Any, port: Optional[int]) -> tuple[bool, str]:
        ip = _ip(host)
        if ip is None:
            name = str(host).lower().rstrip(".")
            if name == "localhost":
                return True, "loopback name"
            if name in self.policy.pinned_names:
                return True, "pinned allowlisted name"
            return False, "unresolved name outside allowlist"
        if ip.is_loopback:
            return True, "loopback"
        if ip.is_unspecified:
            return False, "unspecified address"
        for rule in self.policy.rules:
            if rule.matches(ip, port):
                return True, f"allowlist {rule.as_text()}"
        return False, "address outside allowlist"

    def check_connect(self, family: int, address: Any, kind: str = "connect") -> None:
        if family == getattr(socket, "AF_UNIX", object()) or isinstance(address, (str, bytes)):
            return  # local IPC
        if not isinstance(address, tuple) or not address:
            return
        host, port = address[0], (address[1] if len(address) > 1 else None)
        allowed, reason = self.decide_address(host, port)
        target = f"{host}:{port}"
        if not allowed:
            self._deny(kind, target, reason, SovereignEgressDenied)
        self._allow_first_use(kind, target, reason)

    def check_resolve(self, host: Any, port: Any = None) -> None:
        if host in (None, "", b""):
            return
        name = host.decode() if isinstance(host, bytes) else str(host)
        allowed, reason = self.decide_address(name, port if isinstance(port, int) else None)
        if not allowed:
            self._deny("dns", name, reason, SovereignEgressDenied)

    def check_location(self, location: str, *, kind: str) -> str:
        """Admit a storage location or ingestion source; return it unchanged."""
        text = str(location)
        if _is_remote_location(text):
            parts = urlsplit(text)
            host = parts.hostname or ""
            # A remote location is admitted only when its host is itself an
            # allowed egress target; cloud object-store URLs (s3://bucket,
            # az://container, gs://...) name buckets, never allowlisted hosts,
            # so they are refused in private and air-gapped mode alike.
            allowed, reason = (
                self.decide_address(host, parts.port) if host else (False, "no host")
            )
            if not allowed:
                self._deny(kind, text, reason, SovereignBoundaryDenied)
            self._record("allowed", kind=kind, target=text, reason=reason)
            return text
        path = Path(text[7:] if text.startswith("file://") else text).resolve()
        if self.policy.storage_roots and not any(
            path == root or root in path.parents for root in self.policy.storage_roots
        ):
            self._deny(kind, str(path), "outside declared storage roots", SovereignBoundaryDenied)
        self._record("allowed", kind=kind, target=str(path), reason="local path")
        return text

    # -- the hook ----------------------------------------------------------

    def _hook(self, event: str, args: tuple[Any, ...]) -> None:
        if not event.startswith(("socket.", "subprocess.", "os.system", "os.exec", "os.posix_spawn")):
            return
        if getattr(self._local, "busy", False):
            return
        if event == "socket.connect":
            sock, address = args
            self.check_connect(getattr(sock, "family", None), address)
        elif event in ("socket.sendto", "socket.sendmsg"):
            sock, address = args
            if address is not None:
                self.check_connect(getattr(sock, "family", None), address, kind="send")
        elif event == "socket.getaddrinfo":
            self.check_resolve(args[0], args[1] if len(args) > 1 else None)
        elif event == "socket.gethostbyname":
            self.check_resolve(args[0])
        elif event == "socket.gethostbyaddr":
            self.check_resolve(args[0])
        elif event in ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn"):
            executable = args[0] if args else None
            self._record("process_spawned", kind=event, executable=str(executable)[:256])

    def install_hook(self) -> None:
        if self._hook_installed:
            return
        sys.addaudithook(self._hook)
        self._hook_installed = True
        self._record("hook_installed", events=[
            "socket.connect", "socket.sendto", "socket.sendmsg", "socket.getaddrinfo",
            "socket.gethostbyname", "socket.gethostbyaddr", "subprocess.Popen",
        ])

    # -- evidence ----------------------------------------------------------

    def denial_counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        with self._lock:
            for (kind, _target), count in self._denials.items():
                out[kind] = out.get(kind, 0) + count
        return out

    def attestation(self) -> dict[str, Any]:
        records = self.audit.records
        head = records[-1]["record_hash"] if records else "GENESIS"
        unsigned = {
            "schema": SCHEMA_ATTESTATION,
            "issued_at": int(time.time()),
            "policy": self.policy.as_public_dict(),
            "policy_digest": self.policy.digest,
            "enforcement": {
                "in_process_audit_hook": self._hook_installed,
                "hook_installed_at": self.installed_at,
                "network_isolation_declared": self.policy.network_isolation,
                "boundary_note": (
                    "the in-process hook is defence in depth; the network boundary is "
                    "the container network and is probed separately"
                ),
            },
            "process": {
                "role": self.role,
                "pid": os.getpid(),
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "hostname": socket.gethostname(),
            },
            "build": {"commit": os.environ.get(ENV_BUILD) or _git_commit()},
            "audit": {
                "path": str(self.policy.audit_path),
                "records": len(records),
                "head_hash": head,
                "chain_valid": HashChainAudit.verify(records),
            },
            "denials": self.denial_counts(),
            "key_id": self.policy.key_id,
            "signature_algorithm": "HMAC-SHA256",
        }
        signature = hmac.new(self.policy.attestation_key, canonical_json(unsigned), hashlib.sha256)
        signed = {**unsigned, "signature": signature.hexdigest()}
        self._record("attestation_issued", attestation_digest=digest(signed),
                     audit_head_hash=head, audit_records=len(records))
        return signed


def _git_commit() -> str:
    head = Path(__file__).resolve().parents[1] / ".git" / "HEAD"
    try:
        ref = head.read_text(encoding="utf-8").strip()
        if ref.startswith("ref: "):
            return (head.parent / ref[5:]).read_text(encoding="utf-8").strip()
        return ref
    except OSError:
        return "unknown"


def verify_attestation(
    document: Mapping[str, Any],
    key: bytes,
    audit_records: Optional[Iterable[Mapping[str, Any]]] = None,
) -> dict[str, Any]:
    """Check an attestation's signature and, optionally, its audit anchor.

    ``audit_records`` is the exported chain. It may have grown since the
    attestation was issued; the record at the attested position must carry
    the attested head hash and the whole chain must verify.
    """
    unsigned = {k: v for k, v in document.items() if k != "signature"}
    expected = hmac.new(key, canonical_json(unsigned), hashlib.sha256).hexdigest()
    result: dict[str, Any] = {
        "signature_valid": hmac.compare_digest(expected, str(document.get("signature", ""))),
        "key_id_matches": document.get("key_id") == hashlib.sha256(key).hexdigest()[:16],
    }
    if audit_records is not None:
        records = list(audit_records)
        attested = document.get("audit", {})
        count = int(attested.get("records", 0))
        result["chain_valid"] = HashChainAudit.verify(records)
        anchor = records[count - 1]["record_hash"] if 0 < count <= len(records) else "GENESIS"
        result["audit_anchor_matches"] = anchor == attested.get("head_hash")
        if not result["chain_valid"]:
            result["first_broken_record"] = _first_break(records)
    result["valid"] = all(v for k, v in result.items() if k != "first_broken_record")
    return result


def _first_break(records: list[Mapping[str, Any]]) -> Optional[int]:
    for index in range(1, len(records) + 1):
        if not HashChainAudit.verify(records[:index]):
            return index - 1
    return None


# ---------------------------------------------------------------------------
# Process installation
# ---------------------------------------------------------------------------

_PLANE: Optional[SovereignControlPlane] = None
_PLANE_LOCK = threading.Lock()


def active() -> Optional[SovereignControlPlane]:
    return _PLANE


def install_from_env(
    env: Optional[Mapping[str, str]] = None, *, role: Optional[str] = None
) -> Optional[SovereignControlPlane]:
    """Install the boundary for this process; ``None`` in connected mode.

    Raises :class:`SovereignConfigError` when the configuration is invalid --
    callers must refuse to start rather than run unbounded.
    """
    global _PLANE
    env = os.environ if env is None else env
    with _PLANE_LOCK:
        if _PLANE is not None:
            return _PLANE
        policy = load_policy(env)
        if not policy.enforcing:
            return None
        plane = SovereignControlPlane(policy, role=role or env.get(ENV_ROLE) or "process")
        plane.install_hook()
        _PLANE = plane
        return plane


def admit_location(location: str, *, kind: str = "storage") -> str:
    """Boundary check for ingestion sources and storage locations.

    A no-op in connected mode; in private/air-gapped mode a remote location
    outside the allowlist (and any cloud object store when air-gapped) raises
    :class:`SovereignBoundaryDenied` and is recorded.
    """
    plane = _PLANE
    return location if plane is None else plane.check_location(location, kind=kind)


def worker_argv(script: str | Path, env: Optional[Mapping[str, str]] = None) -> list[str]:
    """argv for a supervised Python worker: wrapped when sovereign mode is on."""
    env = os.environ if env is None else env
    mode = (env.get(ENV_MODE) or "connected").strip().lower().replace("-", "_")
    if mode == "connected":
        return [sys.executable, str(script)]
    return [sys.executable, "-m", "al_haras.sovereign_exec", str(script)]


def read_audit(path: Path) -> list[dict[str, Any]]:
    records = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m al_haras.sovereign_control")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="validate the policy from the environment")
    attest = sub.add_parser("attest", help="issue a signed attestation for this host")
    attest.add_argument("--out", type=Path)
    verify = sub.add_parser("verify", help="verify an attestation (and its audit chain)")
    verify.add_argument("attestation", type=Path)
    verify.add_argument("--audit", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            policy = load_policy()
            print(json.dumps({**policy.as_public_dict(), "policy_digest": policy.digest}, indent=2))
            return 0
        if args.command == "attest":
            plane = install_from_env(role="attest-cli")
            if plane is None:
                print("connected mode: no sovereign boundary to attest", file=sys.stderr)
                return 2
            document = plane.attestation()
            text = json.dumps(document, indent=2, sort_keys=True)
            if args.out:
                args.out.write_text(text + "\n", encoding="utf-8")
            print(text)
            return 0
        policy = load_policy()
        document = json.loads(args.attestation.read_text(encoding="utf-8"))
        records = read_audit(args.audit) if args.audit else None
        result = verify_attestation(document, policy.attestation_key, records)
        print(json.dumps(result, indent=2))
        return 0 if result["valid"] else 1
    except SovereignConfigError as exc:
        print(f"sovereign configuration error: {exc}", file=sys.stderr)
        return 78


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

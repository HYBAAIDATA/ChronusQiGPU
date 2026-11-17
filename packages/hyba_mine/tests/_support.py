# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Shared test support: import paths, a share-verifying Stratum pool, TLS, temp homes.

``VerifyingPool`` extends ``chronus.execution.master_e2e_engine.LocalStratumTestServer``
(the fixture PR #28 rebuilt from the real Bitcoin block 0 coinbase). It speaks
Stratum V1 over a real socket, optionally TLS, and accepts a share only after
rebuilding the header from the job it issued (``compute_merkle_root``,
``swap_endian_words``, ``build_block_header``) and checking SHA-256d against
the difficulty it pushed (``check_share_difficulty_exact``). It never
auto-accepts. With extranonce1 "" and extranonce2 00000001 its "genesis" job
reproduces the real genesis header, so nonce 2083236893 is a known answer.

With ``version_rolling`` set it answers BIP310 ``mining.configure`` by granting
the intersection of the requested mask and its own, and verifies 6-param
submits by rebuilding the version as ``(job & ~mask) | (bits & mask)`` under
the mask it negotiated on that connection (or pushed later).
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import ipaddress
import json
import os
import shutil
import ssl
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

_HERE = Path(__file__).resolve()
_REPO = _HERE.parents[3]
for _path in (_REPO / "packages" / "hyba_mine" / "src", _REPO / "src", _REPO / "packages" / "turing" / "src"):
    if _path.is_dir() and str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

# Route-selection tests must not compile and self-test a real GPU on the developer machine.
# test_opencl.py opts back in explicitly (fake pyopencl, or the real device when present).
os.environ.setdefault("HYBA_MINE_DISABLE_OPENCL", "1")

from chronus.execution.master_e2e_engine import (  # noqa: E402
    GENESIS_COINBASE_HEX,
    LocalStratumTestServer,
    build_block_header,
    check_share_difficulty_exact,
    compute_merkle_root,
    swap_endian_words,
)

from hyba_mine.credentials import FileStore, PoolLogin  # noqa: E402
from hyba_mine.logsafe import register_login  # noqa: E402
from hyba_mine.paths import Layout  # noqa: E402
from hyba_mine.pools import PoolEndpoint  # noqa: E402

REPO_ROOT = _REPO
PACKAGE_ROOT = _REPO / "packages" / "hyba_mine"
GENESIS_NONCE = 2083236893
GENESIS_EN2 = bytes.fromhex("00000001")
SENTINEL_USER = "hybaSentinelAcctQ7Z.macbook"
SENTINEL_PASSWORD = "pw-SENTINEL-kQ9Zt"


def run(coro, timeout: float = 60.0):
    return asyncio.run(asyncio.wait_for(coro, timeout))


class VerifyingPool(LocalStratumTestServer):
    """In-process Stratum pool that verifies every share it is sent."""

    def __init__(
        self,
        username: str = SENTINEL_USER,
        password: str = SENTINEL_PASSWORD,
        difficulty=Fraction(1),
        extranonce1: str = "",
        tls: tuple | None = None,
        send_notify: bool = True,
        reply_to_submits: bool = True,
        version_rolling: str | None = None,
        configure_reply: dict | None = None,
        configure_silent: bool = False,
        configure_hangup: bool = False,
    ) -> None:
        super().__init__("HYBA test pool", 0)
        self.expected_username = username
        self.expected_password = password
        self.difficulty = Fraction(difficulty)
        self.extranonce1 = extranonce1
        self.tls = tls
        self.send_notify = send_notify
        self.reply_to_submits = reply_to_submits
        self.jobs: dict[str, dict] = {}
        self.current = "genesis"
        self.add_job("genesis", self.ntime)
        self.writers: list[asyncio.StreamWriter] = []
        self.accepted: list = []
        self.rejected: list = []
        self.seen: set = set()
        self.authorized = 0
        self.pings: list = []
        # BIP310: the mask this pool can grant (None: mining.configure is an unknown method).
        self.version_rolling = version_rolling
        self.configure_reply = configure_reply
        self.configure_silent = configure_silent
        # A legacy pool that closes the connection on mining.configure (an unknown method).
        self.configure_hangup = configure_hangup
        self.methods: list[str] = []
        self.configure_params: list = []
        self.masks: dict = {}

    # ------------------------------------------------------------- jobs
    def add_job(self, job_id: str, ntime: str) -> None:
        self.jobs[job_id] = {
            "prevhash": self.prevhash_stratum,
            "coinb1": self.coinb1,
            "coinb2": self.coinb2,
            "merkle_branch": list(self.merkle_branch),
            "version": self.version,
            "nbits": self.nbits,
            "ntime": ntime,
        }

    def notify_message(self, job_id: str, clean: bool) -> dict:
        job = self.jobs[job_id]
        return {
            "id": None,
            "method": "mining.notify",
            "params": [job_id, job["prevhash"], job["coinb1"], job["coinb2"], job["merkle_branch"],
                       job["version"], job["nbits"], job["ntime"], clean],
        }

    def difficulty_message(self) -> dict:
        value = self.difficulty
        number = int(value) if value.denominator == 1 else float(value)
        return {"id": None, "method": "mining.set_difficulty", "params": [number]}

    async def broadcast(self, message: dict) -> None:
        line = (json.dumps(message) + "\n").encode()
        for writer in list(self.writers):
            if not writer.is_closing():
                writer.write(line)
                with contextlib.suppress(ConnectionError):
                    await writer.drain()

    async def push_job(self, job_id: str, ntime: str, clean: bool = True) -> None:
        if clean:
            self.jobs = {}
        self.add_job(job_id, ntime)
        self.current = job_id
        await self.broadcast(self.notify_message(job_id, clean))

    async def push_difficulty(self, difficulty) -> None:
        self.difficulty = Fraction(difficulty)
        await self.broadcast(self.difficulty_message())

    async def push_version_mask(self, mask_hex: str) -> None:
        for writer in list(self.writers):
            self.masks[writer] = int(mask_hex, 16)
        await self.broadcast({"id": None, "method": "mining.set_version_mask", "params": [mask_hex]})

    def configure(self, params, writer) -> dict:
        self.configure_params.append(params)
        if self.configure_reply is not None:
            reply = self.configure_reply
            mask = reply.get("version-rolling.mask")
            if reply.get("version-rolling") is True and isinstance(mask, str):
                try:
                    self.masks[writer] = int(mask, 16)
                except ValueError:
                    pass
            return {"result": reply, "error": None}
        if self.version_rolling is None:
            return {"result": None, "error": [20, "Unknown method", None]}
        ok = (isinstance(params, list) and len(params) == 2 and isinstance(params[0], list)
              and "version-rolling" in params[0] and isinstance(params[1], dict))
        requested = params[1].get("version-rolling.mask") if ok else None
        min_bits = params[1].get("version-rolling.min-bit-count") if ok else None
        if (not isinstance(requested, str) or len(requested) != 8 or not isinstance(min_bits, int)
                or isinstance(min_bits, bool)):
            return {"result": None, "error": [20, "Malformed configure", None]}
        try:
            granted = int(requested, 16) & int(self.version_rolling, 16)
        except ValueError:
            return {"result": None, "error": [20, "Malformed configure", None]}
        self.masks[writer] = granted
        return {"result": {"version-rolling": True, "version-rolling.mask": f"{granted:08x}"}, "error": None}

    async def drop_connections(self) -> None:
        for writer in list(self.writers):
            writer.close()
        self.writers.clear()

    # ------------------------------------------------------- verification
    def verify(self, params: list, mask: int | None = None) -> tuple:
        if not isinstance(params, list) or len(params) not in (5, 6):
            return False, [20, "Malformed submit", None]
        worker, job_id, en2_hex, ntime_hex, nonce_hex = params[:5]
        vb_hex = params[5] if len(params) == 6 else None
        if worker != self.expected_username:
            return False, [24, "Unauthorized worker", None]
        job = self.jobs.get(job_id)
        if job is None:
            return False, [21, "Job not found", None]
        if len(str(en2_hex)) != self.extranonce2_size * 2 or ntime_hex != job["ntime"] or len(str(nonce_hex)) != 8:
            return False, [20, "Malformed submit", None]
        version = int(job["version"], 16)
        if vb_hex is not None:
            if mask is None:
                return False, [20, "Version rolling not negotiated", None]
            if not isinstance(vb_hex, str) or len(vb_hex) != 8:
                return False, [20, "Malformed submit", None]
            try:
                bits = int(vb_hex, 16)
            except ValueError:
                return False, [20, "Malformed submit", None]
            if bits & ~mask:
                return False, [20, "Version bits outside the negotiated mask", None]
            version = (version & ~mask) | (bits & mask)  # BIP310
        key = (job_id, en2_hex, ntime_hex, nonce_hex, vb_hex)
        if key in self.seen:
            return False, [22, "Duplicate share", None]
        try:
            merkle = compute_merkle_root(job["coinb1"], self.extranonce1, en2_hex, job["coinb2"], job["merkle_branch"])
            header = build_block_header(version, swap_endian_words(job["prevhash"]), merkle,
                                        ntime_hex, job["nbits"], int(nonce_hex, 16))
        except (TypeError, ValueError):
            return False, [20, "Malformed submit", None]
        ok, block_hash, _hash_int, _target = check_share_difficulty_exact(header, self.difficulty)
        if not ok:
            return False, [23, "Low difficulty share", None]
        self.seen.add(key)
        return True, block_hash

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.writers.append(writer)
        try:
            async for raw in reader:
                try:
                    message = json.loads(raw.decode().strip())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if "method" not in message:
                    if message.get("result") == "pong":
                        self.pings.append(message)
                    continue
                method, request_id, params = message["method"], message.get("id"), message.get("params", [])
                self.methods.append(method)
                reply = None
                pushes = []
                if method == "mining.configure":
                    if self.configure_hangup:
                        self.configure_params.append(params)
                        break
                    if self.configure_silent:
                        self.configure_params.append(params)
                        continue
                    reply = {"id": request_id, **self.configure(params, writer)}
                elif method == "mining.subscribe":
                    reply = {"id": request_id, "result": [[["mining.set_difficulty", "d"], ["mining.notify", "n"]],
                                                         self.extranonce1, self.extranonce2_size], "error": None}
                elif method == "mining.extranonce.subscribe":
                    reply = {"id": request_id, "result": True, "error": None}
                elif method == "mining.authorize":
                    ok = params == [self.expected_username, self.expected_password]
                    reply = {"id": request_id, "result": ok, "error": None if ok else [24, "Unauthorized worker", None]}
                    if ok:
                        self.authorized += 1
                        pushes.append(self.difficulty_message())
                        if self.send_notify:
                            pushes.append(self.notify_message(self.current, True))
                elif method == "mining.submit":
                    if not self.reply_to_submits:
                        continue
                    ok, detail = self.verify(params, self.masks.get(writer))
                    if ok:
                        self.accepted.append((params, detail))
                        reply = {"id": request_id, "result": True, "error": None}
                    else:
                        self.rejected.append((params, detail))
                        reply = {"id": request_id, "result": None, "error": detail}
                else:
                    reply = {"id": request_id, "result": None, "error": [20, "Unknown method", None]}
                for item in [reply, *pushes]:
                    if item is not None:
                        writer.write((json.dumps(item) + "\n").encode())
                await writer.drain()
        except (ConnectionError, OSError):
            pass
        finally:
            if writer in self.writers:
                self.writers.remove(writer)
            self.masks.pop(writer, None)
            writer.close()

    async def start(self) -> None:
        context = None
        if self.tls is not None:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(*self.tls)
        self.server = await asyncio.start_server(self.handle_client, "127.0.0.1", 0, ssl=context)
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        await self.drop_connections()
        if self.server is not None:
            self.server.close()

    def endpoint(self) -> PoolEndpoint:
        return PoolEndpoint("127.0.0.1", self.port, self.tls is not None)


def genesis_job_check() -> bool:
    """The fixture's coinbase with extranonce2 00000001 is the real genesis coinbase."""
    return "01" + "00000001" + GENESIS_COINBASE_HEX[10:] == GENESIS_COINBASE_HEX


def self_signed_cert(directory: Path) -> tuple[str, str]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "hyba-mine-test-pool")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                                                    x509.DNSName("localhost")]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    certfile = directory / "pool-cert.pem"
    keyfile = directory / "pool-key.pem"
    certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    keyfile.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.NoEncryption()))
    return str(certfile), str(keyfile)


def fs_keeps_permissions(directory: Path) -> bool:
    """True when chmod 0600 sticks (APFS, ext4); some mounted volumes ignore it."""
    probe = directory / ".mode-probe"
    probe.write_text("x")
    os.chmod(probe, 0o600)
    kept = (probe.stat().st_mode & 0o077) == 0
    probe.unlink()
    return kept


class MemoryStore:
    """Credential store test double used where the test filesystem ignores chmod."""

    backend = "memory"

    def __init__(self) -> None:
        self._data: dict = {}

    def get(self, pool_id: str):
        login = self._data.get(pool_id)
        if login is not None:
            register_login(login.username, login.password)
        return login

    def put(self, pool_id: str, login: PoolLogin) -> None:
        register_login(login.username, login.password)
        self._data[pool_id] = login

    def delete(self, pool_id: str) -> bool:
        return self._data.pop(pool_id, None) is not None


class TempHome:
    """A HYBA Mine home and log directory in a fresh temporary directory."""

    def __enter__(self) -> "TempHome":
        self.root = Path(tempfile.mkdtemp(prefix="hyba-mine-test-"))
        self.layout = Layout(self.root / "home", self.root / "logs").prepare()
        self._env = {k: os.environ.get(k) for k in ("HYBA_MINE_HOME", "HYBA_MINE_LOG_DIR", "CHRONUS_HASHRATE_LIMIT_FILE")}
        os.environ["HYBA_MINE_HOME"] = str(self.layout.home)
        os.environ["HYBA_MINE_LOG_DIR"] = str(self.layout.logs)
        # A published hashrate limit on the developer machine must not change the cap under test.
        self.cap_limit_file = self.root / "hashrate-cap"
        os.environ["CHRONUS_HASHRATE_LIMIT_FILE"] = str(self.cap_limit_file)
        self.file_permissions = fs_keeps_permissions(self.layout.home)
        self._memory = MemoryStore()
        return self

    def store(self):
        if self.file_permissions:
            return FileStore(self.layout.credentials)
        return self._memory

    def put_login(self, pool_id: str, username: str = SENTINEL_USER, password: str = SENTINEL_PASSWORD) -> PoolLogin:
        login = PoolLogin(username, password)
        self.store().put(pool_id, login)
        return login

    def __exit__(self, *exc) -> None:
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.root, ignore_errors=True)


class FakeClock:
    """Integer nanosecond clock that only moves when a test advances it."""

    def __init__(self, start: int = 0) -> None:
        self.now_ns = start

    def __call__(self) -> int:
        return self.now_ns

    def advance(self, seconds: float) -> None:
        self.now_ns += int(seconds * 1e9)


def fake_sleeper(clock: FakeClock, waits: list | None = None):
    """A CapGate sleeper that advances ``clock`` instead of sleeping."""

    async def sleeper(seconds: float, stop: asyncio.Event) -> None:
        if waits is not None:
            waits.append(seconds)
        clock.advance(seconds)
        await asyncio.sleep(0)

    return sleeper


def small_cap(rate: int, clock: FakeClock):
    from chronus.execution.hashrate_cap import HashrateCap

    return HashrateCap(rate, clock=clock)

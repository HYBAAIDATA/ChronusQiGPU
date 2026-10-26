"""Bounded subprocess execution; canonical TURING remains the computation owner."""

import hashlib
import hmac
import json
import stat
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from .control import Unavailable, canonical, digest


class ProcessRuntime:
    def __init__(
        self,
        *,
        timeout=60,
        memory_bytes=4 * 1024**3,
        output_bytes=16 * 1024**2,
        command=None,
        cancel_check=None,
    ):
        if (
            not 1 <= timeout <= 3600
            or memory_bytes < 128 * 1024**2
            or not 1024 <= output_bytes <= 128 * 1024**2
        ):
            raise ValueError("invalid execution limits")
        self.timeout = timeout
        self.memory_bytes = memory_bytes
        self.output_bytes = output_bytes
        self.command = command or [sys.executable, "-m", "hyba_turing_service.worker_child"]
        self.cancel_check = cancel_check or (lambda: False)

    def run(self, request):
        env = {
            k: os.environ[k] for k in ("PATH", "LANG", "LC_ALL", "SYSTEMROOT") if k in os.environ
        }
        # Libraries are installed in the worker image. Never forward credentials,
        # PYTHONPATH, user site packages, cloud metadata tokens or API environment.
        env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", PYTHONNOUSERSITE="1")
        # Limits are set in a tiny exec wrapper, not a threaded preexec_fn.
        limits = [self.memory_bytes, self.output_bytes, max(1, int(self.timeout)), 128]
        wrapper = (
            "import os,resource,sys,json; a,f,c,n=json.loads(sys.argv[1]);"
            "resource.setrlimit(resource.RLIMIT_AS,(a,a));"
            "resource.setrlimit(resource.RLIMIT_FSIZE,(f,f));"
            "resource.setrlimit(resource.RLIMIT_CPU,(c,c));"
            "resource.setrlimit(resource.RLIMIT_NOFILE,(n,n));"
            "os.execvpe(sys.argv[2],sys.argv[2:],os.environ)"
        )
        with (
            tempfile.TemporaryDirectory(prefix="turing-job-") as working,
            tempfile.TemporaryFile() as output,
            tempfile.TemporaryFile() as errors,
            tempfile.TemporaryFile() as input_file,
        ):
            input_file.write(canonical(request).encode())
            input_file.seek(0)
            proc = subprocess.Popen(
                [sys.executable, "-c", wrapper, json.dumps(limits), *self.command],
                stdin=input_file,
                stdout=output,
                stderr=errors,
                cwd=working,
                env=env,
                start_new_session=True,
                close_fds=True,
            )
            deadline = time.monotonic() + self.timeout
            try:
                while proc.poll() is None:
                    if time.monotonic() >= deadline or self.cancel_check():
                        raise Unavailable("execution deadline or cancellation")
                    time.sleep(0.02)
                if proc.returncode != 0:
                    raise Unavailable("canonical worker failed")
                output.seek(0)
                raw = output.read(self.output_bytes + 1)
                if len(raw) > self.output_bytes:
                    raise Unavailable("result size exceeded")
                report = json.loads(raw)
                if not isinstance(report, dict):
                    raise Unavailable("invalid worker envelope")
                return report
            finally:
                # Always fence the entire process group, including descendants
                # left behind by a child that already exited.
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()


class ResultCustody:
    """Tenant-keyed durable service reports, not a replacement algebraic custody."""

    def __init__(self, root, *, integrity_key=None, previous_integrity_keys=()):
        keys = (() if integrity_key is None else (integrity_key,)) + tuple(previous_integrity_keys)
        if any(not isinstance(key, bytes) or len(key) < 32 for key in keys):
            raise ValueError("custody integrity keys must contain at least 32 bytes")
        if integrity_key is None and keys:
            raise ValueError("historical keys require a current signing key")
        self._integrity_keys = keys
        if Path(root).is_symlink():
            raise ValueError("custody root must not be a symlink")
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.is_symlink():
            raise ValueError("custody root must not be a symlink")

    def commit(self, tenant, job, report):
        import hashlib

        directory = self.root / hashlib.sha256(tenant.encode()).hexdigest()
        directory.mkdir(mode=0o700, exist_ok=True)
        if directory.is_symlink():
            raise Unavailable("unsafe custody path")
        raw = canonical(report).encode()
        checksum = hashlib.sha256(raw).hexdigest()
        path = directory / (hashlib.sha256(job.encode()).hexdigest() + ".json")
        # Same job identity cannot be silently overwritten by another result.
        if path.exists():
            if path.is_symlink() or path.read_bytes() != raw:
                raise Unavailable("custody identity conflict")
            return checksum
        fd, temp = tempfile.mkstemp(dir=directory, prefix=".pending-")
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temp, path)
            except FileExistsError:
                if path.is_symlink() or path.read_bytes() != raw:
                    raise Unavailable("custody conflict")
            dirfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
        finally:
            os.unlink(temp)
        return checksum

    def _paths(self, tenant, job):
        directory = self.root / hashlib.sha256(tenant.encode()).hexdigest()
        if directory.is_symlink():
            raise Unavailable("unsafe custody path")
        base = hashlib.sha256(job.encode()).hexdigest()
        return directory / (base + ".json"), directory / (base + ".receipt")

    @staticmethod
    def _read(path, limit):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                raise Unavailable("invalid custody entry")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                raw = stream.read(limit + 1)
            if len(raw) > limit:
                raise Unavailable("custody entry too large")
            return raw
        finally:
            os.close(fd)

    def commit_execution(self, tenant, job, request, report, *, admission_hash):
        """Write a service recovery receipt, not a second mathematical authority.

        Legacy unsigned reports remain readable by their original consumers but
        cannot be promoted through recovery. Keys never enter the worker child.
        """
        checksum = self.commit(tenant, job, report)
        if not self._integrity_keys:
            return checksum
        if not isinstance(admission_hash, str) or not admission_hash:
            raise Unavailable("admitted request identity required for recovery")
        body = dict(
            schema="turing.service-recovery.v1",
            tenant=tenant,
            job=job,
            request_digest=digest(request),
            admission_hash=admission_hash,
            report_digest=checksum,
        )
        signature = hmac.new(
            self._integrity_keys[0], canonical(body).encode(), hashlib.sha256
        ).hexdigest()
        raw = canonical(dict(body=body, signature=signature)).encode()
        _, path = self._paths(tenant, job)
        fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".receipt-")
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temp, path)
            except FileExistsError:
                # Rotation does not overwrite a prior valid receipt.
                self.recover(tenant, job, request, admission_hash=admission_hash)
            dirfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
        finally:
            os.unlink(temp)
        return checksum

    def recover(self, tenant, job, request, *, admission_hash):
        """Authenticate retained service output. Never invoke a computation."""
        try:
            if not self._integrity_keys:
                raise Unavailable("authenticated recovery is not configured")
            report_path, receipt_path = self._paths(tenant, job)
            receipt = json.loads(self._read(receipt_path, 16384))
            body, signature = receipt["body"], receipt["signature"]
            if not isinstance(signature, str) or not any(
                hmac.compare_digest(
                    signature, hmac.new(key, canonical(body).encode(), hashlib.sha256).hexdigest()
                )
                for key in self._integrity_keys
            ):
                raise Unavailable("recovery receipt authentication failed")
            if (
                body["schema"] != "turing.service-recovery.v1"
                or body["tenant"] != tenant
                or body["job"] != job
                or body["request_digest"] != digest(request)
                or body["admission_hash"] != admission_hash
            ):
                raise Unavailable("recovery receipt does not bind this admission")
            raw = self._read(report_path, 128 * 1024**2)
            if hashlib.sha256(raw).hexdigest() != body["report_digest"]:
                raise Unavailable("retained report integrity failed")
            report = json.loads(raw)
            if not isinstance(report, dict) or digest(report) != body["report_digest"]:
                raise Unavailable("retained report is not canonical")
            return report
        except Exception:
            raise Unavailable("authenticated recovery evidence unavailable or invalid") from None

    def purge(self, tenant):
        import hashlib

        directory = self.root / hashlib.sha256(tenant.encode()).hexdigest()
        if not directory.exists():
            return
        if directory.is_symlink():
            raise Unavailable("unsafe custody purge path")
        for path in directory.iterdir():
            if path.is_symlink() or not path.is_file():
                raise Unavailable("unexpected custody entry")
            path.unlink()
        directory.rmdir()


class DurableRuntime:
    def __init__(self, runtime, custody, tenant, job, *, admission_hash=None):
        self.admission_hash = admission_hash
        self.runtime = runtime
        self.custody = custody
        self.tenant = tenant
        self.job = job

    def run(self, request):
        report = self.runtime.run(request)
        self.custody.commit_execution(
            self.tenant, self.job, request, report, admission_hash=self.admission_hash
        )
        return report

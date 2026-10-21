"""Bounded subprocess execution; canonical TURING remains the computation owner."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from .control import Unavailable, canonical


class ProcessRuntime:
    def __init__(
        self,
        *,
        timeout=60,
        memory_bytes=4 * 1024**3,
        output_bytes=16 * 1024**2,
        command=None,
        cancel_check=None
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
        with tempfile.TemporaryDirectory(
            prefix="turing-job-"
        ) as working, tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors, tempfile.TemporaryFile() as input_file:
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

    def __init__(self, root):
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
    def __init__(self, runtime, custody, tenant, job):
        self.runtime = runtime
        self.custody = custody
        self.tenant = tenant
        self.job = job

    def run(self, request):
        report = self.runtime.run(request)
        self.custody.commit(self.tenant, self.job, report)
        return report

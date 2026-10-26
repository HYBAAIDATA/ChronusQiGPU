"""Software GPIU composition: Chronus execution, OVID state, THESEUS discovery."""

from dataclasses import replace
import os
from pathlib import Path
import secrets

from aethel.enterprise.journal import FileLock, _fsync_directory
from aethel.enterprise.ovid_state import OvidEnterpriseState, TheseusStateIndex
from .scaled_gpiu import ScaledGPIU
from .virtual_igpu.abi import Workload, execution_policy_for_product_mode
from .virtual_igpu.runtime import RuntimeDaemon


def _local_key(root):
    """Persist a private software identity; deployments may supply a managed key."""
    path = root / "ovid.key"
    with FileLock(root / "identity.lock"):
        if not path.exists():
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(secrets.token_bytes(32))
                stream.flush()
                os.fsync(stream.fileno())
            _fsync_directory(root)
        key = path.read_bytes()
        if len(key) != 32:
            raise ValueError("invalid persisted OVID identity")
        return key


class ChronusTriad:
    def __init__(
        self,
        root,
        *,
        tenant,
        mode="independent",
        host_adapter_id=None,
        allow_software_fallback=True,
        hmac_key=None,
        adapters=None,
        admission_policy=None,
        custody_options=None,
    ):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.tenant = tenant
        key = hmac_key if hmac_key is not None else _local_key(self.root)
        self.ovid = OvidEnterpriseState(
            self.root / "ovid", tenant=tenant, hmac_key=key, **(custody_options or {})
        )
        self.theseus = TheseusStateIndex(self.root / "theseus", self.ovid)
        self.runtime = RuntimeDaemon(
            self.root / "execution" / self.ovid.engine._safe_tenant(tenant),
            adapters=adapters,
            custody=self.ovid,
            hmac_key=key,
            admission_policy=admission_policy,
        )
        self.capacity = ScaledGPIU(
            self,
            tenant=tenant,
            mode=mode,
            host_adapter_id=host_adapter_id,
            allow_software_fallback=allow_software_fallback,
        )

    @property
    def adapters(self):
        return self.runtime.adapters

    def submit(self, workload):
        if workload.tenant != self.tenant:
            raise PermissionError("triad tenant mismatch")
        workload = replace(workload)  # Validate the caller's identity before adding custody.
        workload = replace(
            workload,
            content_hash=None,
            constraints={**(workload.constraints or {}), "custody": "required"},
        )
        return self.runtime.submit(workload)

    def execute(self, **kwargs):
        return self.capacity.execute(**kwargs)

    def pythia(self, *, workload_id, header80, target, nonces):
        return self.submit(
            Workload(
                id=workload_id,
                tenant=self.tenant,
                kind="sha256d_scan",
                input={
                    "header80_hex": bytes(header80).hex(),
                    "target_hex": bytes(target).hex(),
                    "nonces": list(nonces),
                },
                execution_policy=(
                    "required_adapter"
                    if self.capacity.host_adapter_id
                    else execution_policy_for_product_mode(self.capacity.product_mode)
                ),
                required_adapter_id=self.capacity.host_adapter_id,
                allow_software_fallback=self.capacity.allow_software_fallback,
            )
        )

    def query(self, *, workload_id=None, producer=None):
        return self.theseus.query(tenant=self.tenant, workload_id=workload_id, producer=producer)

    def checkpoint(self, label=""):
        return self.ovid.checkpoint(self.tenant, label)

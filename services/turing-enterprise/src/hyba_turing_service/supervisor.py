"""Small durable queue consumer. Multiple processes share admission/claim locks."""

import time
from .control import Conflict, Denied, Unavailable
from .runtime import ProcessRuntime, ResultCustody, DurableRuntime


class Supervisor:
    def __init__(
        self, factory, token_factory, actor, custody_root, *, runtime_factory=None, custody=None
    ):
        self.factory = factory
        self.token_factory = token_factory
        self.actor = actor
        self.custody = custody if custody is not None else ResultCustody(custody_root)
        self.stopping = False
        self.runtime_factory = runtime_factory or (
            lambda cancel: ProcessRuntime(cancel_check=cancel)
        )

    def run_once(self):
        plane = self.factory()
        try:
            token = self.token_factory()
            plane._authorize(
                token, self.actor, "__service_ops__", "turing.ops.execute", operator=True
            )
            candidates = plane.db.execute(
                "SELECT j.tenant,j.job,j.actor,j.request_hash FROM jobs j JOIN customers c ON c.tenant=j.tenant WHERE j.state='admitted' AND c.state='active' AND c.starts<=? AND c.expires>? ORDER BY j.rowid LIMIT 100",
                (plane.clock(), plane.clock()),
            ).fetchall()
            for row in candidates:
                tenant, job, submitter, admission_hash = row

                def cancelled():
                    if self.stopping:
                        return True
                    other = self.factory()
                    try:
                        try:
                            other._before_dispatch(tenant, submitter, job)
                        except Denied:
                            return True
                        return False
                    finally:
                        other.close()

                runtime = DurableRuntime(
                    self.runtime_factory(cancelled),
                    self.custody,
                    tenant,
                    job,
                    admission_hash=admission_hash,
                )
                try:
                    plane.execute(
                        self.token_factory(), self.actor, tenant=tenant, job=job, runtime=runtime
                    )
                    return True
                except Denied:
                    # The worker credential was verified above. Revalidate it
                    # before treating current project/membership denial as terminal.
                    plane._authorize(
                        self.token_factory(),
                        self.actor,
                        "__service_ops__",
                        "turing.ops.execute",
                        operator=True,
                    )
                    with plane._transaction():
                        changed = plane.db.execute(
                            "UPDATE jobs SET state='cancelled' WHERE tenant=? AND job=? AND state='admitted'",
                            (tenant, job),
                        ).rowcount
                        if changed:
                            plane._audit(
                                tenant, self.actor, "policy_cancel_before_dispatch", dict(job=job)
                            )
                except (Conflict, Unavailable):
                    # Another worker may have claimed it; an unknown outcome is
                    # already quarantined. Never reset running jobs for retry.
                    continue
            return False
        finally:
            plane.close()

    def run(self):
        while not self.stopping:
            if not self.run_once():
                time.sleep(0.5)

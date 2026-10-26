"""Exact telemetry certificates and authorized, fenced cohort recovery.

The diagonal contraction model has a proved invariant box R_i=d_i/(1-q_i).
Certificates check observed transitions against that model; observations that
violate its disturbance bound are rejected. This is no claim about unobserved
hardware dynamics. Recovery uses the existing authority and uncertain-commit
latch, and never treats a smaller approximate tensor as an exact replacement.
"""

from dataclasses import dataclass, replace
import json
from fractions import Fraction

from chronus.fleet.recovery_security import LatchState, BlindRetryForbiddenError


def _exact(value):
    if type(value) is not int and not isinstance(value, Fraction):
        raise TypeError("telemetry/model values require exact integers or rationals")
    return Fraction(value)


@dataclass(frozen=True)
class CohortModel:
    contraction: tuple[Fraction, ...]
    disturbance: tuple[Fraction, ...]

    def __post_init__(self):
        q, d = tuple(map(_exact, self.contraction)), tuple(map(_exact, self.disturbance))
        if (
            not q
            or len(q) != len(d)
            or len(q) > 16
            or any(not 0 <= v < 1 for v in q)
            or any(v < 0 for v in d)
        ):
            raise ValueError("contractive model requires matching q in [0,1), d>=0")
        object.__setattr__(self, "contraction", q)
        object.__setattr__(self, "disturbance", d)

    @property
    def invariant_box(self):
        return tuple(d / (1 - q) for q, d in zip(self.contraction, self.disturbance))

    def state(self, observation):
        state = tuple(map(_exact, observation))
        if len(state) != len(self.contraction) or any(x < 0 for x in state):
            raise ValueError("nonnegative telemetry of declared dimension required")
        return state

    def lyapunov(self, observation):
        state = self.state(observation)
        return sum(max(Fraction(0), x - r) ** 2 for x, r in zip(state, self.invariant_box))

    def certify_transition(self, before, after):
        before, after = self.state(before), self.state(after)
        if any(
            y > q * x + d for x, y, q, d in zip(before, after, self.contraction, self.disturbance)
        ):
            raise ValueError("observed transition violates model disturbance bound")
        old, new = self.lyapunov(before), self.lyapunov(after)
        factor = max(self.contraction) ** 2
        if new > factor * old:
            raise ArithmeticError("Lyapunov contraction invariant failed")

        def pair(q):
            return [q.numerator, q.denominator]

        return {
            "before": list(map(pair, before)),
            "after": list(map(pair, after)),
            "invariant_box": list(map(pair, self.invariant_box)),
            "lyapunov_before": pair(old),
            "lyapunov_after": pair(new),
            "contraction_bound": pair(factor),
            "finite_time_log_ratio": None if not old or not new else {"log": pair(new / old)},
            "verified": True,
        }


class CohortRecovery:
    def __init__(self, scheduler, controller, journal):
        self.scheduler, self.controller, self.journal = scheduler, controller, journal

    def _check_pending_intents(self):
        self.journal.verify_and_recover_journal()
        if not self.journal.journal_path.exists():
            return
        frames = [
            json.loads(line)["body"] for line in self.journal.journal_path.read_text().splitlines()
        ]
        completed = {
            f["operation_id"][:-9] for f in frames if f["operation_id"].endswith(":complete")
        }
        for frame in frames:
            operation = frame["operation_id"]
            if operation.endswith(":intent") and operation[:-7] not in completed:
                self.journal.mark_uncertain(
                    operation_id=operation, detail="recovery intent has no durable completion"
                )
                raise BlindRetryForbiddenError("unfinished recovery requires reconciliation")

    def recover(
        self, *, worker_id, tenant, new_lanes, operation_id, grant, resources, capacity, now_ms=None
    ):
        worker = self.scheduler.workers.get(worker_id)
        if worker is None or worker.identity.tenant != tenant or resources.tenant_id != tenant:
            raise PermissionError("recovery worker must belong to admitted tenant")
        if type(new_lanes) is not int or not 1 <= new_lanes <= worker.plan.lanes:
            raise ValueError("recovery lanes must be positive and within admitted capacity")
        if self.journal.state != LatchState.HEALTHY:
            raise BlindRetryForbiddenError("recovery requires reconciliation of uncertain custody")
        self._check_pending_intents()
        old_token = worker.identity.current_fencing_token
        plan = replace(worker.plan, lanes=new_lanes)

        def mutation():
            if self.scheduler.workers[worker_id].identity.current_fencing_token != old_token:
                raise ValueError("worker generation changed before recovery")
            self.journal.commit(
                operation_id=operation_id + ":intent",
                payload={
                    "worker": worker_id,
                    "tenant": tenant,
                    "old_generation": worker.identity.generation,
                    "new_lanes": new_lanes,
                },
            )
            try:
                identity = self.scheduler.terminate_worker(worker_id, replacement_plan=plan)
                result = {
                    "worker": worker_id,
                    "generation": identity.generation,
                    "new_lanes": new_lanes,
                    "fencing_token": identity.current_fencing_token,
                }
                self.journal.commit(operation_id=operation_id + ":complete", payload=result)
                return result
            except BaseException as exc:
                if self.journal.state == LatchState.HEALTHY:
                    self.journal.mark_uncertain(
                        operation_id=operation_id, detail=type(exc).__name__
                    )
                raise

        def verify(result):
            current = self.scheduler.workers[worker_id]
            return (
                current.identity.current_fencing_token == result["fencing_token"]
                and current.identity.current_fencing_token != old_token
                and current.plan.lanes == new_lanes
            )

        return self.controller.admit_and_execute(
            grant=grant,
            resource_vector=resources,
            workload_id=operation_id,
            owner_authority="Salamander",
            capacity=capacity,
            expected_version=capacity.current_state_version,
            mutation_fn=mutation,
            postcondition_fn=verify,
            now_ms=now_ms,
        )


class CohortAutonomicLoop:
    """One bounded observe/control/observe cycle using a caller-owned sensor.

    The sensor returns exact, nonnegative telemetry in the model's declared
    units. A grant provider signs the concrete recovery request. No background
    thread, authority key or fabricated telemetry is owned by this controller.
    """

    def __init__(self, recovery, model, sensor, grant_provider):
        self.recovery, self.model = recovery, model
        self.sensor, self.grant_provider = sensor, grant_provider

    def step(self, *, worker_id, tenant, operation_id):
        worker = self.recovery.scheduler.workers.get(worker_id)
        if worker is None or worker.identity.tenant != tenant:
            raise PermissionError("telemetry worker must belong to tenant")
        before = self.model.state(self.sensor(worker_id, tenant))
        if self.model.lyapunov(before) == 0:
            return {"action": "hold", "invariant_region": True}
        from chronus.lucas_engine import lucas

        smaller = [lucas(i) for i in range(1, 20) if lucas(i) < worker.plan.lanes]
        lanes = max(smaller, default=1)
        request = dict(
            worker_id=worker_id, tenant=tenant, new_lanes=lanes, operation_id=operation_id
        )
        authorization = self.grant_provider(dict(request))
        result = self.recovery.recover(**request, **authorization)
        if not result.postcondition_verified:
            return {"action": "refused", "recovery_verified": False}
        after = self.model.state(self.sensor(worker_id, tenant))
        try:
            certificate = self.model.certify_transition(before, after)
        except ValueError:
            return {
                "action": "reconfigured",
                "recovery_verified": True,
                "stability_verified": False,
                "reason": "observed disturbance bound exceeded",
            }
        return {
            "action": "reconfigured",
            "recovery_verified": True,
            "stability_verified": True,
            "certificate": certificate,
        }

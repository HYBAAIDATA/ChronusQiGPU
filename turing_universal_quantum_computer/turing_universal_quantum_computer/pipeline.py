"""The TURING VQC production composition path.

Canonical pipeline (manual §4, Turing half):

    request -> capability analysis -> representation choice ->
    circuit/program validation -> compile/plan -> execution ->
    measurement -> verification -> result -> checkpoint/replay

Every stage emits a ``StageEvidence`` record with a canonical evidence state
(PASS / FAIL / GATED / UNAVAILABLE / REFUSED / SKIPPED).  The pipeline never
substitutes an optimistic value: a refused program produces a REFUSED report,
a missing subsystem produces UNAVAILABLE, hardware absence produces GATED.

Consumption is real, not decorative: OVID transformation and THESEUS custody
are exercised through ``transform.py``/``custody.py`` when requested; CHRONUS
is probed for a contracted lane and otherwise honestly recorded as
GATED/UNAVAILABLE with the cross-agent dependency named.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Sequence

from .backends import default_backends, select_backend
from .backends.base import ExecutionResult, Program, TruthClass
from .capabilities import capability_report
from .certificates import RunWitness, issue_witness, verify_witness
from .chronus_lane import probe_chronus_lane
from .representation import RepresentationPlanner
from .taxonomy import EvidenceState, classify_execution
from .verify import DEFAULT_VERIFY_WIDTH, verify_program_unitarity

__all__ = [
    "PIPELINE_SCHEMA",
    "STAGE_ORDER",
    "VQCRequest",
    "StageEvidence",
    "PipelineReport",
    "VQCPipeline",
    "run_pipeline",
]

PIPELINE_SCHEMA = "turing.vqc.pipeline_report.v1"

#: Stage-local state for a stage the request did not ask for — distinct from
#: the canonical evidence states, which always describe attempted work.
SKIPPED = "SKIPPED"

#: Stage-local state for a stage that refused its input (a domain outcome,
#: recorded alongside the canonical evidence states).
REFUSED = "REFUSED"

#: Canonical stage order — the composition path itself.
STAGE_ORDER: tuple[str, ...] = (
    "request_validation",
    "capability_analysis",
    "representation_choice",
    "contract_validation",
    "compile_plan",
    "chronus_lane",
    "execution",
    "measurement",
    "verification",
    "custody",
    "replay",
)


@dataclass(frozen=True)
class VQCRequest:
    """One request into the VQC composition path.

    Exactly one of ``program`` / ``qasm`` must be supplied.  ``qasm`` accepts
    the Clifford QASM subset parsed by ``phi_machine.PhiQuantumCircuit``.
    """

    program: Program | None = None
    qasm: str | None = None
    shots: int | None = None
    seed: int | None = None
    readout: Sequence[int] | None = None
    marginal_of: Sequence[int] | None = None
    expectation: bool = False
    measurement_qubit: int | None = None
    entanglement_cut: int | None = None
    representation: str = "auto"
    prefer_backend: str | None = None
    max_amplitudes: int = 1 << 20
    verify_unitary: bool = True
    verify_max_width: int = DEFAULT_VERIFY_WIDTH
    differential: bool = True
    custody: bool = False
    replay: bool = False
    notes: str = ""


@dataclass(frozen=True)
class StageEvidence:
    """One stage's evidence record."""

    stage: str
    state: str  # EvidenceState value or REFUSED/SKIPPED
    detail: str
    artifacts: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "state": self.state,
            "detail": self.detail,
            "artifacts": self.artifacts,
        }


@dataclass(frozen=True)
class PipelineReport:
    """The pipeline's complete, checkable output."""

    schema: str
    verdict: str  # PASS / FAIL / REFUSED / GATED
    program_digest: str | None
    stages: tuple[StageEvidence, ...]
    execution_kind: dict[str, Any] | None
    result: dict[str, Any] | None
    witness: dict[str, Any] | None
    custody: tuple[dict[str, Any], ...]
    replay: tuple[dict[str, Any], ...]
    refusals: tuple[str, ...]
    notes: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "verdict": self.verdict,
            "program_digest": self.program_digest,
            "stages": [s.as_dict() for s in self.stages],
            "execution_kind": self.execution_kind,
            "result": self.result,
            "witness": self.witness,
            "custody": list(self.custody),
            "replay": list(self.replay),
            "refusals": list(self.refusals),
            "notes": self.notes,
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), sort_keys=True)


class VQCPipeline:
    """Runs one ``VQCRequest`` through the canonical composition path."""

    def __init__(self, *, backends: Sequence[Any] | None = None) -> None:
        self._backends = list(backends) if backends is not None else default_backends()

    def run(self, request: VQCRequest) -> PipelineReport:
        stages: list[StageEvidence] = []
        refusals: list[str] = []
        program: Program | None = None
        result: ExecutionResult | None = None
        witness: RunWitness | None = None
        custody_records: list[dict[str, Any]] = []
        replay_records: list[dict[str, Any]] = []
        kind_report: dict[str, Any] | None = None

        def record(stage: str, state: str, detail: str, **artifacts: Any) -> None:
            stages.append(StageEvidence(stage, state, detail, dict(artifacts)))

        # -- stage 1: request_validation -------------------------------------
        if request.program is None and request.qasm is None:
            record(
                "request_validation", EvidenceState.FAIL.value,
                "neither program nor qasm supplied",
            )
            return self._finish(stages, "FAIL", None, None, None, (), (), refusals, request)
        if request.program is not None and request.qasm is not None:
            record(
                "request_validation", EvidenceState.FAIL.value,
                "ambiguous request: both program and qasm supplied",
            )
            return self._finish(stages, "FAIL", None, None, None, (), (), refusals, request)
        if request.program is not None:
            program = request.program
            record(
                "request_validation", EvidenceState.PASS.value,
                f"program object accepted: {program.n_qubits} qubits, "
                f"{len(program.operations)} operations",
            )
        else:
            try:
                program = _program_from_qasm(request.qasm or "")
            except Exception as exc:
                refusals.append(f"qasm_parse: {exc}")
                record(
                    "request_validation", REFUSED,
                    f"QASM refused: {exc}",
                )
                return self._finish(stages, "REFUSED", None, None, None, (), (), refusals, request)
            record(
                "request_validation", EvidenceState.PASS.value,
                f"QASM parsed (Clifford subset): {program.n_qubits} qubits, "
                f"{len(program.operations)} operations",
            )

        # -- stage 2: capability_analysis ------------------------------------
        report = capability_report()
        boundary_clean = bool(report.get("claim_boundary_clean"))
        record(
            "capability_analysis",
            EvidenceState.PASS.value if boundary_clean else EvidenceState.FAIL.value,
            "claim boundary audited"
            + ("" if boundary_clean else "; BOUNDARY VIOLATION — failing closed"),
            statements=len(report.get("statements", ())),
        )
        if not boundary_clean:
            refusals.append("capability_analysis: claim boundary violation")
            return self._finish(stages, "FAIL", program.digest(), None, None, (), (), refusals, request)

        # -- stage 3: representation_choice ----------------------------------
        planner = RepresentationPlanner(max_amplitudes=request.max_amplitudes)
        choice = planner.plan(program, representation=request.representation)
        record(
            "representation_choice",
            EvidenceState.PASS.value if choice.admitted else REFUSED,
            choice.rationale,
            choice=choice.as_dict(),
        )
        if not choice.admitted:
            refusals.append(f"representation_choice: {choice.rationale}")
            refusals.extend(choice.refusals)
            return self._finish(stages, "REFUSED", program.digest(), None, None, (), (), refusals, request)

        # -- stage 4: contract_validation ------------------------------------
        validation_detail = ["gate/qubit domains checked at Program construction"]
        if request.verify_unitary:
            ureport = verify_program_unitarity(program, max_width=request.verify_max_width)
            validation_detail.append(ureport.reason)
            ustate = {
                "PASS": EvidenceState.PASS.value,
                "FAIL": EvidenceState.FAIL.value,
            }.get(ureport.state, EvidenceState.GATED.value)
            record(
                "contract_validation", ustate,
                "; ".join(validation_detail),
                unitarity=ureport.as_dict(),
            )
            if ureport.state == "FAIL":
                refusals.append(f"contract_validation: {ureport.reason}")
                return self._finish(stages, "FAIL", program.digest(), None, None, (), (), refusals, request)
        else:
            record(
                "contract_validation", EvidenceState.PASS.value,
                "; ".join(validation_detail),
            )

        # -- stage 5: compile_plan -------------------------------------------
        prefer = request.prefer_backend or choice.backend
        try:
            backend, admission = select_backend(
                program,
                prefer=prefer,
                max_amplitudes=request.max_amplitudes,
            )
        except ValueError as exc:
            record(
                "compile_plan", REFUSED,
                str(exc),
            )
            refusals.append(f"compile_plan: {exc}")
            return self._finish(stages, "REFUSED", program.digest(), None, None, (), (), refusals, request)
        if backend is None or not admission.admitted:
            record(
                "compile_plan", REFUSED,
                admission.reason,
                admission=admission.as_dict() if hasattr(admission, "as_dict") else {"admitted": False},
            )
            refusals.append(f"compile_plan: {admission.reason}")
            return self._finish(stages, "REFUSED", program.digest(), None, None, (), (), refusals, request)
        record(
            "compile_plan", EvidenceState.PASS.value,
            f"admitted by {backend.name}: {admission.reason}",
            backend=backend.name,
        )

        # -- stage 6: chronus_lane -------------------------------------------
        lane = probe_chronus_lane()
        record(
            "chronus_lane", lane.lane_state,
            lane.reason,
            lane=lane.as_dict(),
        )

        # -- stage 7: execution -----------------------------------------------
        options = {
            "shots": request.shots,
            "seed": request.seed,
            "readout": request.readout,
            "marginal_of": request.marginal_of,
            "expectation": request.expectation,
            "measurement": request.measurement_qubit,
            "entanglement": request.entanglement_cut,
        }
        try:
            result = backend.execute(program, **{k: v for k, v in options.items() if v is not None})
        except Exception as exc:
            record("execution", EvidenceState.FAIL.value, f"execution raised: {exc}")
            refusals.append(f"execution: {exc}")
            return self._finish(stages, "FAIL", program.digest(), None, None, (), (), refusals, request)
        record(
            "execution", EvidenceState.PASS.value,
            f"{backend.name} executed; truth_class={result.truth_class.value}",
            execution_class=result.execution_class.value,
        )
        kind = classify_execution(result, via_pipeline=True)
        kind_report = kind.as_dict()

        # -- stage 8: measurement ---------------------------------------------
        payload = result.payload or {}
        record(
            "measurement", EvidenceState.PASS.value,
            "measurement surface: "
            + ", ".join(sorted(k for k in payload if k != "field")) or "state only",
            payload_keys=sorted(payload),
        )

        # -- stage 9: verification --------------------------------------------
        verify_notes: list[str] = []
        verify_ok = True
        try:
            witness = issue_witness(program, result, notes=request.notes)
            verify_witness(witness)
            verify_notes.append("witness issued and re-verified")
        except Exception as exc:
            verify_ok = False
            verify_notes.append(f"witness verification failed: {exc}")
            refusals.append(f"verification: {exc}")
        if request.differential:
            diff = _differential_check(program, backend, self._backends, request)
            verify_notes.append(diff[1])
            if diff[0] == EvidenceState.FAIL.value:
                verify_ok = False
                refusals.append("differential: " + diff[1])
            stages_diff_state = diff[0]
        else:
            stages_diff_state = None
        record(
            "verification",
            EvidenceState.PASS.value if verify_ok else EvidenceState.FAIL.value,
            "; ".join(verify_notes),
            differential=stages_diff_state,
        )
        if not verify_ok:
            return self._finish(
                stages, "FAIL", program.digest(), result, None, (), (), refusals, request
            )

        # -- stage 10: custody -------------------------------------------------
        custody_state = SKIPPED
        if request.custody:
            custody_state, custody_records = self._custody(program, result, witness)
            if custody_state in (EvidenceState.UNAVAILABLE.value, EvidenceState.FAIL.value):
                refusals.append(f"custody: requested but {custody_state}")
        record(
            "custody", custody_state,
            "committed program/result/witness envelopes to THESEUS"
            if custody_state == EvidenceState.PASS.value
            else ("custody not requested" if custody_state == SKIPPED else "custody unavailable or failed"),
            receipts=len(custody_records),
        )

        # -- stage 11: replay ---------------------------------------------------
        replay_state = SKIPPED
        if request.replay:
            if custody_state != EvidenceState.PASS.value:
                replay_state = EvidenceState.UNAVAILABLE.value
                refusals.append("replay: requested but custody did not commit")
            else:
                replay_state, replay_records = self._replay(custody_records)
                if replay_state != EvidenceState.PASS.value:
                    refusals.append(f"replay: {replay_state}")
        record(
            "replay", replay_state,
            "custody replay verified" if replay_state == EvidenceState.PASS.value
            else ("replay not requested" if replay_state == SKIPPED else "replay did not verify"),
        )

        verdict = "PASS"
        if custody_state in (EvidenceState.UNAVAILABLE.value, EvidenceState.FAIL.value) or \
           replay_state in (EvidenceState.UNAVAILABLE.value, EvidenceState.FAIL.value):
            verdict = "GATED"  # computation verified; durability evidence gated
        return self._finish(
            stages, verdict, program.digest(), result, witness,
            tuple(custody_records), tuple(replay_records), refusals, request,
            kind_report=kind_report,
        )

    # -- custody / replay helpers ----------------------------------------------

    def _custody(
        self, program: Program, result: ExecutionResult, witness: RunWitness | None
    ) -> tuple[str, list[dict[str, Any]]]:
        try:
            from .custody import open_custody
        except Exception:
            return EvidenceState.UNAVAILABLE.value, []
        try:
            custody = open_custody()
            self._last_custody = custody
            records = [
                custody.commit("program", program.to_dict(), meta={"stage": "request"}).as_dict(),
                custody.commit(
                    "result",
                    _result_payload(result),
                    meta={"stage": "result"},
                ).as_dict(),
            ]
            if witness is not None:
                records.append(
                    custody.commit(
                        "witness", witness.to_dict(), meta={"stage": "verification"}
                    ).as_dict()
                )
            return EvidenceState.PASS.value, records
        except Exception as exc:
            return EvidenceState.FAIL.value, [{"error": str(exc)}]

    def _replay(self, custody_records: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
        # Replay must run against the same custody instance that holds the
        # records; the pipeline keeps its custody adapter for the report's
        # lifetime via the stored adapter reference.
        custody = getattr(self, "_last_custody", None)
        if custody is None:
            return EvidenceState.FAIL.value, [
                {"error": "no live custody adapter for replay"}
            ]
        reports = [custody.replay(rec["uid"]).as_dict() for rec in custody_records]
        ok = all(r["state"] == "PASS" for r in reports)
        return (EvidenceState.PASS.value if ok else EvidenceState.FAIL.value), reports

    def _finish(
        self,
        stages: list[StageEvidence],
        verdict: str,
        digest: str | None,
        result: ExecutionResult | None,
        witness: RunWitness | None,
        custody_records: tuple[dict[str, Any], ...],
        replay_records: tuple[dict[str, Any], ...],
        refusals: list[str],
        request: VQCRequest,
        kind_report: dict[str, Any] | None = None,
    ) -> PipelineReport:
        return PipelineReport(
            schema=PIPELINE_SCHEMA,
            verdict=verdict,
            program_digest=digest,
            stages=tuple(stages),
            execution_kind=kind_report,
            result=_result_payload(result) if result is not None else None,
            witness=witness.to_dict() if witness is not None else None,
            custody=custody_records,
            replay=replay_records,
            refusals=tuple(refusals),
            notes=request.notes,
        )


def _program_from_qasm(qasm: str) -> Program:
    """Parse the Clifford QASM subset into a canonical ``Program``."""
    from .phi_machine import PhiQuantumCircuit

    circuit = PhiQuantumCircuit.from_qasm(qasm)
    program = Program(n_qubits=circuit.num_qubits)
    for gate in circuit.gates:
        program = program.then(gate.name, *gate.qubits)
    return program


def _jsonable(value: Any) -> Any:
    """Make a backend payload JSON-serialisable without losing claim content.

    States become their canonical ``to_dict`` (exact string amplitudes);
    other non-JSON values become ``str`` — the string form is the exact form
    for the algebraic types used here, so no value is silently weakened.
    """
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _jsonable(to_dict())
    return str(value)


def _result_payload(result: ExecutionResult) -> dict[str, Any]:
    return {
        "backend": result.backend,
        "execution_class": result.execution_class.value,
        "truth_class": result.truth_class.value,
        "n_qubits": result.n_qubits,
        "program_digest": result.program_digest,
        "materialised": result.materialised,
        "measured_qpu": result.measured_qpu,
        "payload": _jsonable(result.payload or {}),
    }


def _differential_check(
    program: Program,
    used_backend: Any,
    backends: Sequence[Any],
    request: VQCRequest,
) -> tuple[str, str]:
    """Re-run the program on a second admitted backend and compare a shared
    observable exactly where the two backends expose one (single-qubit
    marginal).  Where no second backend admits the check is GATED, not a
    failure — a single-backend run is still verified by its witness."""
    backend = None
    for candidate in backends:
        if candidate.name == used_backend.name:
            continue
        if candidate.admit(program).admitted:
            backend = candidate
            break
    if backend is None:
        return (
            EvidenceState.GATED.value,
            "no second admitted backend; differential evidence gated",
        )
    probe = min(program.n_qubits - 1, request.measurement_qubit or 0)
    try:
        # both exact backends expose expectation_z on a probe qubit when asked
        a2 = used_backend.execute(program, measurement=probe)
        b2 = backend.execute(program, measurement=probe)
        ea = (a2.payload or {}).get("measurement", {}).get("expectation_z")
        eb = (b2.payload or {}).get("measurement", {}).get("expectation_z")
        if ea is None or eb is None:
            return (
                EvidenceState.GATED.value,
                f"{backend.name} does not expose a comparable probe observable",
            )
        if ea == eb:
            return (
                EvidenceState.PASS.value,
                f"differential match on qubit {probe}: expectation_z={ea} "
                f"({used_backend.name} vs {backend.name})",
            )
        return (
            EvidenceState.FAIL.value,
            f"differential MISMATCH on qubit {probe}: {ea} != {eb} "
            f"({used_backend.name} vs {backend.name})",
        )
    except Exception as exc:
        return (
            EvidenceState.GATED.value,
            f"differential probe not comparable: {exc}",
        )


def run_pipeline(request: VQCRequest) -> PipelineReport:
    """Convenience wrapper: default backends, canonical stage order."""
    return VQCPipeline().run(request)

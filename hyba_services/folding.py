"""Fold/operator registries and evidence-bearing execution."""

from __future__ import annotations

import time
import uuid
from typing import Any
from typing import Callable
from typing import Mapping

from hyba_contracts import FoldContract
from hyba_contracts import FoldMode
from hyba_contracts import OperatorContract
from hyba_contracts import ResultReceipt


class UnsupportedPairing(ValueError):
    pass


class FoldExecutor:
    def __init__(
        self,
        folds: Mapping[str, FoldContract],
        operators: Mapping[str, OperatorContract],
        proof: Callable[..., Any],
        sign: Callable[[dict], str],
    ):
        self.folds = folds
        self.operators = operators
        self.proof = proof
        self.sign = sign

    def execute(
        self, obj, family: str, operator: str, run_folded: Callable, run_exact: Callable
    ) -> ResultReceipt:
        if family not in self.folds or operator not in self.operators:
            raise UnsupportedPairing(operator)
        fold = self.folds[family]
        op = self.operators[operator]
        if (
            family not in op.accepted_fold_families
            or operator not in fold.supported_operators
            or op.mode is FoldMode.REJECT
        ):
            raise UnsupportedPairing(f"{operator}/{family}")
        started = time.perf_counter_ns()
        rehydrations = 0
        if op.mode is FoldMode.REHYDRATE:
            exact = fold.decode(obj.pisot_fold, obj.residual_boundary)
            output = run_exact(exact, op)
            folded, residual = fold.encode(output)
            rehydrations = 1
        else:
            folded, residual = run_folded(obj.pisot_fold, obj.residual_boundary, op)
            output = fold.decode(folded, residual)
        proof = self.proof(op, obj, output, op.output_invariants)
        body = {
            "receipt_id": str(uuid.uuid4()),
            "operator": operator,
            "input_object_id": obj.object_id,
            "output_object_id": getattr(output, "object_id", str(output)),
            "mode": op.mode,
            "rehydration_count": rehydrations,
            "residual": residual,
            "invariants_checked": op.output_invariants,
            "proof_id": proof.proof_id,
            "backend_certificate": proof.backend_certificate,
            "bytes_moved": len(repr(folded).encode()),
            "latency_ms": str((time.perf_counter_ns() - started) / 1_000_000),
            "lineage": (obj.object_id, proof.proof_id),
        }
        receipt = ResultReceipt(**body, signature=self.sign(body))
        receipt.validate()
        return receipt

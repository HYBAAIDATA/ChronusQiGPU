"""Proof 3: the seam produces real, verifiable attestations."""

from __future__ import annotations

from chronus.seam import Result, run
from chronus.seam.attest_compose import CompositeAttestation, attest_compose
from chronus.seam.types import Err, ThresholdPolicy


def run_and_attest(job: dict, fleet=None, policy: ThresholdPolicy = ThresholdPolicy.majority) -> Result[CompositeAttestation]:
    result = run(job, fleet)
    if isinstance(result, Err):
        return result
    links = [r.attestation for r in result.value.results]
    return attest_compose(links, policy)

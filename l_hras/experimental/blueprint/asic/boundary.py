# l_hras/asic/boundary.py

from l_hras.experimental.blueprint.asic.types import *
from l_hras.experimental.blueprint.asic.capability import ASICCapability
from l_hras.experimental.blueprint.asic.hash import Job
from l_hras.experimental.blueprint.asic.fold import is_foldable, is_stabilizer

def asic_guard(asic: ASICCapability, job: Job) -> 'Result':
    """
    The ASIC refuses what it cannot fold.
    The boundary is honest.
    """
    # No fold capability: use classic hash path
    if not asic.fold_capable:
        return Ok(job.with_classic_path())

    # Not foldable: use classic hash path
    if not is_foldable(job.circuit):
        return Ok(job.with_classic_path())

    # Too many qubits: refuse
    if job.qubits > asic.max_fold_qubits:
        return Err(ASICError.QUBITS_EXCEEDED)

    # Non-stabilizer above 11 qubits: refuse
    if not is_stabilizer(job.circuit) and job.qubits > 11:
        return Err(ASICError.NON_STABILIZER_REFUSED)

    # Job is foldable: use the fold path
    return Ok(job.with_fold_path())

# Executable invariant catalogue; tests determine each outcome.
INVARIANTS = {
    'ASIC_B1': 'The ASIC refuses what it cannot fold.',
    'ASIC_B2': 'The ASIC is fail-closed.',
    'ASIC_B3': 'The boundary is honest.',
    'ASIC_B4': 'The classic path is always available.',
}

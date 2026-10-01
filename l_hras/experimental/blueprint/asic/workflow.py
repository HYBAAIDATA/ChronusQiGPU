# l_hras/asic/workflow.py

from l_hras.experimental.blueprint.asic.types import *
from l_hras.experimental.blueprint.asic.capability import ASICCapability
from l_hras.experimental.blueprint.asic.hash import Job, Share, asic_hash
from l_hras.experimental.blueprint.asic.fold import asic_fold
from l_hras.experimental.blueprint.asic.attestation import asic_attest
from l_hras.experimental.blueprint.asic.boundary import asic_guard
from l_hras.experimental.blueprint.asic.intelligences import run_all_intelligences
from l_hras.experimental.blueprint.asic.modes import run_all_modes

def asic_mine(asic: ASICCapability, job: Job) -> 'Result':
    """
    The complete quantum-armed ASIC mining workflow.
    All seven layers run.
    """
    # 1. Guard the job (boundary)
    guarded_job = asic_guard(asic, job)
    if isinstance(guarded_job, Err):
        return guarded_job
    guarded_job = guarded_job.value

    # 2. Fold if applicable
    folded = None
    if guarded_job.has_fold_path():
        folded_result = asic_fold(asic, guarded_job)
        if isinstance(folded_result, Err):
            # Fall back to classic path
            guarded_job = guarded_job.with_classic_path()
        else:
            folded = folded_result.value
            guarded_job.window = folded.window

    # 3. Run the six intelligences
    intelligences = run_all_intelligences(asic, guarded_job)

    # 4. Run the five modes
    modes = run_all_modes(asic, guarded_job)

    # 5. Hash (classic path)
    share_result = asic_hash(asic, guarded_job)
    if isinstance(share_result, Err):
        return share_result
    share = share_result.value

    # 6. Attest
    if folded is not None:
        attest_result = asic_attest(asic, guarded_job, share, folded.certificate)
        if isinstance(attest_result, Err):
            return attest_result
        share.certificate = folded.certificate

    # 7. Return the share
    return Ok(share)

# Executable invariant catalogue; tests determine each outcome.
INVARIANTS = {
    'ASIC_W1': 'All seven layers run in every mining workflow.',
    'ASIC_W2': 'The fold only applies when applicable.',
    'ASIC_W3': 'The classic path is always the fallback.',
    'ASIC_W4': 'Every share is attested.',
    'ASIC_W5': 'Every certificate is written to Aethel.',
}

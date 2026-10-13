"""SCALE1–SCALE10 admission/evidence report, with unknowns preserved."""
import math

def scaling_report(*, budget_bytes=100_000_000_000, image_bytes=None, cache_bytes=0,
                   completed_hashes=0, elapsed_seconds=1.0, attested=False,
                   replayed=False, trusted_head_verified=False, genetic_observations=0,
                   exact_valid=False, native_available=False, overlay_available=False,
                   pipeline_available=False, floor_hps=10**19, witness_qubits=10000):
    if any(type(v)is not int or v<0 for v in (budget_bytes,cache_bytes,completed_hashes,genetic_observations,witness_qubits)) or not budget_bytes or not witness_qubits:raise ValueError('bounded nonnegative accounting values required')
    if image_bytes is not None and(type(image_bytes)is not int or image_bytes<0):raise ValueError('invalid measured image size')
    if not math.isfinite(elapsed_seconds)or elapsed_seconds<=0:raise ValueError('measured positive elapsed duration required')
    hps=completed_hashes/elapsed_seconds
    checks={
      'SCALE1':None if image_bytes is None else image_bytes<=budget_bytes,
      'SCALE2':None if image_bytes is None else image_bytes+cache_bytes<=budget_bytes,
      'SCALE3':{'native':bool(native_available),'physical_overlay':bool(overlay_available),'temporal_pipeline':bool(pipeline_available)},
      'SCALE4':{'representation_dimension_exponent':witness_qubits,'ratio_expression':f'2^{witness_qubits}/{witness_qubits}','hash_equivalence_established':False,'used_as_hashrate_multiplier':False},
      'SCALE5':hps>=floor_hps,'SCALE6':bool(attested),'SCALE7':bool(replayed),
      'SCALE8':bool(trusted_head_verified),'SCALE9':genetic_observations>=3,'SCALE10':bool(exact_valid)}
    return {'schema':'chronos_scaling_evidence_v1','checks':checks,'completed_sha256d_hashes':completed_hashes,'elapsed_seconds':elapsed_seconds,'measured_hashrate':hps,'floor_hps':floor_hps,'floor_met':checks['SCALE5'],'storage_budget_bytes':budget_bytes,'image_bytes':image_bytes,'cache_bytes':cache_bytes,'conditions':'The supplied notes are retained; represented dimension is not an execution counter. SCALE8 requires an externally retained trusted chain head.'}

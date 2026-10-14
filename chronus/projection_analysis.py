"""Exact fibers of the v1 matrix-coordinate rung projection.

Domain is finite 2*h-bit DIGESTS, not arbitrary-length headers or floating 11D
vectors. Header preimages are not bounded by the digest-domain fiber count.
"""
from collections import Counter
from .pythi_native import matrix_fold, matrix_unfold

def _parameters(half_bits,rung_bits,index):
    if type(half_bits) is not int or not 1<=half_bits<=128 or type(rung_bits) is not int or not 1<=rung_bits<=half_bits or type(index) is not int or not 1<=index<=256:
        raise ValueError('bounded coordinate and projection dimensions required')

def projection_contract(rung_bits=8,half_bits=128,index=31):
    _parameters(half_bits,rung_bits,index)
    k=1<<(2*half_bits-rung_bits)
    return {'schema':'pythi_projection_analysis_v1','domain':'finite_digest_coordinates',
            'fold':'Q^index mod 2^half_bits','half_bits':half_bits,'fold_index':index,
            'rung_bits':rung_bits,'projection':'1 + (folded_left mod 2^rung_bits)',
            'domain_size':1<<(2*half_bits),'rung_count':1<<rung_bits,
            'preimages_per_rung':k,'entropy_bits_retained':rung_bits,
            'entropy_bits_discarded':2*half_bits-rung_bits,
            'surjective':True,'balanced_for_uniform_digest':True,
            'header_preimage_bound':None,'uniform_headers_proven':False,
            'cryptographic_collision_resistance_claimed':False,
            'ideal_uniform_target_rung_expected_queries':1<<rung_bits,
            'acceptance_identity':'full domain-separated header digest, policy and both folded coordinates; never rung alone',
            'consensus_deployable':False}

def project_digest(digest,rung_bits=8,half_bits=128,index=31):
    _parameters(half_bits,rung_bits,index)
    return 1+(matrix_fold(digest,index,half_bits)[0]&((1<<rung_bits)-1))

def preimage_at(rung,ordinal,rung_bits=8,half_bits=128,index=31):
    """Construct the unique digest for a coordinate-fiber ordinal, without search."""
    _parameters(half_bits,rung_bits,index)
    if type(rung) is not int or not 1<=rung<=1<<rung_bits or type(ordinal) is not int or not 0<=ordinal<1<<(2*half_bits-rung_bits):
        raise ValueError('fiber coordinates outside domain')
    high,right=divmod(ordinal,1<<half_bits)
    left=(high<<rung_bits)+(rung-1)
    return matrix_unfold((left,right),index,half_bits)

def preimage_ordinal(digest,rung_bits=8,half_bits=128,index=31):
    _parameters(half_bits,rung_bits,index)
    left,right=matrix_fold(digest,index,half_bits)
    return (left>>rung_bits)*(1<<half_bits)+right

def exhaustive_projection(half_bits=6,rung_bits=3,index=31):
    _parameters(half_bits,rung_bits,index)
    if half_bits>8:raise ValueError('exhaustive validation limited to 65536 digests')
    counts=Counter();seen=set()
    for digest in range(1<<(2*half_bits)):
        rung=project_digest(digest,rung_bits,half_bits,index)
        ordinal=preimage_ordinal(digest,rung_bits,half_bits,index)
        if preimage_at(rung,ordinal,rung_bits,half_bits,index)!=digest:raise ValueError('constructive fiber inverse failed')
        counts[rung]+=1;seen.add((rung,ordinal))
    k=1<<(2*half_bits-rung_bits)
    if len(seen)!=1<<(2*half_bits) or any(counts[n]!=k for n in range(1,1+(1<<rung_bits))):raise ValueError('unbalanced projection')
    return {'classification':'EXHAUSTIVELY_TESTED_REDUCED_DOMAIN','contract':projection_contract(rung_bits,half_bits,index),'digests_checked':sum(counts.values()),'per_rung_counts':dict(sorted(counts.items())),'fiber_roundtrip':True}

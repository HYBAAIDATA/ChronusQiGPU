"""Deterministic actual encoded-frame corruption and conformance."""
import hashlib
import json
from pathlib import Path

import pytest

from chronus.storage import chrn_frame as frame, chrn_rs257 as ecc
from chronus.security.al_haras import reed_solomon as rs

pytestmark = pytest.mark.real
VECTOR = json.loads((Path(__file__).parent/"vectors"/"chrn_rs257_v11.json").read_text())


def test_recovery_known_answer_and_boundary():
    raw=bytes.fromhex(VECTOR["input_hex"])
    wire=bytes.fromhex(VECTOR["expected_encoded_hex"])
    assert hashlib.sha256(raw).hexdigest()==VECTOR["input_sha256"]
    assert hashlib.sha256(wire).hexdigest()==VECTOR["expected_encoded_sha256"]
    assert ecc.encode(raw)==wire
    assert ecc.decode(wire)==raw
    assert 256 in ecc._unpack_parity(wire[316:],0)[0]
    for case in VECTOR["corruption_cases"]:
        start=frame.HEADER_SIZE+case["body_offset"]
        damaged=rs.inject_faults(wire,range(start,start+case["burst_bytes"]))
        if case["expected_status"]=="reject":
            with pytest.raises(frame.CorruptFrameError):
                ecc.decode_with_report(damaged)
        else:
            result=ecc.decode_with_report(damaged)
            assert result.status==case["expected_status"]
            assert result.data==raw
            assert result.corrected_byte_positions==tuple(case["corrected_positions"])
            assert len(result.corrected_symbols)==64
            assert set(result.corrected_symbols)=={(0,i%8,i//8) for i in range(case["body_offset"],case["body_offset"]+64)}


@pytest.mark.parametrize("size",[0,1,7,8,9,31,32,33,255,256,257,511,512,513])
def test_profile_boundaries(size):
    source=(bytes(range(256))*3)[:size]
    wire=ecc.encode(source)
    assert len(wire)==60+size+144*((size+255)//256)
    assert ecc.encode(source)==wire
    result=ecc.decode_with_report(wire)
    assert result.data==source and result.status=="clean" and not result.corrected_symbols
    with pytest.raises(frame.CorruptFrameError):
        ecc.decode(wire+b"\0")
    with pytest.raises(frame.CorruptFrameError):
        ecc.decode(wire[:-1])


@pytest.mark.parametrize("size,start",[(256,256),(256,224),(9,0),(255,230),(257,380)])
def test_contiguous_wire_burst_in_data_parity_tail_and_block_boundary(size,start):
    source=(bytes(range(256))*2)[:size]
    wire=ecc.encode(source)
    positions=tuple(range(60+start,60+start+64))
    damaged=rs.inject_faults(wire,positions)
    result=ecc.decode_with_report(damaged)
    assert result.data==source and result.status=="corrected"
    assert result.corrected_byte_positions==positions


def test_exact_interleave_bound_for_every_tail_and_wire_start():
    # Count potentially affected GF symbols, not only changed bits.
    # For each byte store the set of (lane,symbol) it overlaps.
    for length in range(1,257):
        touched=[{(i%8,i//8)} for i in range(length)]+[set() for _ in range(144)]
        for s in range(128):
            lane=(s+length)%8
            for byte in range(s*9//8,(s*9+8)//8+1):
                touched[length+byte].add((lane,32+s//8))
        counts={}
        per_lane=[0]*8
        for i,items in enumerate(touched):
            for key in items:
                counts[key]=counts.get(key,0)+1
                if counts[key]==1:
                    per_lane[key[0]]+=1
            if i>=64:
                for key in touched[i-64]:
                    counts[key]-=1
                    if counts[key]==0:
                        per_lane[key[0]]-=1
            assert max(per_lane)<=8


def test_header_unsupported_flags_and_parameter_zero_path():
    raw=ecc.encode(b"abc")
    with pytest.raises(frame.UnsupportedRecoveryError):
        frame.encode(b"",parameters=ecc.PARAMETERS)
    with pytest.raises(frame.HeaderCRCError):
        ecc.decode(raw[:56]+bytes([raw[56]^1])+raw[57:])
    with pytest.raises(frame.InvalidFlagsError):
        ecc.decode(raw[:6]+b"\x80"+raw[7:])
    with pytest.raises(frame.UnsupportedRecoveryError):
        ecc.decode(raw[:7]+b"\x00"+raw[8:])


def test_invalid_parity_label_is_counted_and_repaired():
    wire=bytearray(ecc.encode(bytes(range(256))))
    # First coefficient is 256: change its nine-bit representation to 511.
    wire[316]=255
    wire[317]|=128
    result=ecc.decode_with_report(wire)
    assert result.data==bytes(range(256))
    assert (0,0,32) in result.corrected_symbols
    assert result.corrected_byte_positions==(316,317)


def test_nine_errors_in_single_lane_rejects():
    source=bytes(range(256))
    wire=ecc.encode(source)
    with pytest.raises(frame.CorruptFrameError):
        ecc.decode(rs.inject_faults(wire,[60+i*8 for i in range(9)]))


def test_multiple_shard_recovery_composes_without_changing_algorithms():
    from chronus.storage.erasure import encode_stripe,recover_stripe
    source=bytes(range(256))
    protected=ecc.encode(source)
    stripe,shards=encode_stripe(protected,4)
    parts=list(shards)
    parts[1]=None
    restored=recover_stripe(stripe,tuple(parts))
    damaged=rs.inject_faults(restored,range(60,124))
    assert ecc.decode(damaged)==source

@pytest.mark.parametrize("start,count",[(200,65),(256,72)])
def test_recoverable_beyond_contiguous_guarantee(start,count):
    source=bytes(range(256))
    wire=ecc.encode(source)
    positions=tuple(range(60+start,60+start+count))
    actual=ecc.decode_with_report(rs.inject_faults(wire,positions))
    assert actual.status=="corrected" and actual.data==source
    assert actual.corrected_byte_positions==positions
    counts=[0]*8
    for _,lane,_ in actual.corrected_symbols:
        counts[lane]+=1
    assert max(counts)<=8

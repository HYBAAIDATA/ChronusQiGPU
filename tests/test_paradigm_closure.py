"""Exact executable closure checks; no deployment or hardware inference."""
import hashlib
import subprocess
from fractions import Fraction
from itertools import product

import pytest

from chronus.math.fold_ledger import (
    FoldLedger, FoldedWords, compensating_edit, dedup, fold_residency,
    is_equivariant, keyed_lookup, phi_matrix, pisano_period,
)
from chronus.storage import positional_codec as codec
from chronus.storage.chrn_frame import CorruptFrameError
from chronus.research.torus_certificate import torus_certificate
from chronus.research.paradigm_seal import capacity_address, refusal_registry, seal, verify_seal, validate_findings

pytestmark = pytest.mark.real


def test_sentinel_positional_total():
    assert [codec.decode_byte(codec.encode_byte(i)) for i in range(256)] == list(range(256))
    good = {codec.encode_byte(i) for i in range(256)}
    for digits in product(range(5),repeat=4):
        if digits not in good:
            with pytest.raises(ValueError):
                codec.decode_byte(digits)
    for size in (0,1,255,256,257,513):
        data = (bytes(range(256))*3)[:size]
        frame = codec.encode(data)
        assert len(frame)==60+4*len(data)
        assert codec.decode(frame)==data
        if data:
            altered = bytearray(frame)
            altered[60] = 9
            with pytest.raises(CorruptFrameError):
                codec.decode(bytes(altered))
    for value in (-1,256,True):
        with pytest.raises(ValueError):
            codec.encode_byte(value)


@pytest.mark.parametrize("bits",[8,16,32,64])
def test_sentinel_group_law_and_inverse(bits):
    modulus = 1<<bits
    words = (0,1,modulus-1,modulus//2)
    a = FoldLedger(bits).stage(13).stage(29)
    b = FoldLedger(bits).stage(42)
    assert a.materializations == 0
    result = a.materialize(words)
    assert a.materializations == 1
    assert result == b.materialize(words)
    assert FoldLedger(bits).stage(29).materialize(FoldLedger(bits).stage(13).materialize(words))==result
    assert a.unfold(result)==words
    period = pisano_period(bits)
    # Independently exponentiate the companion matrix without period reduction.
    def raw_power(n):
        a,b,c,d = 1,0,0,1
        e,f,g,h = 1,1,1,0
        while n:
            if n & 1:
                a,b,c,d = ((a*e+b*g)%modulus,(a*f+b*h)%modulus,
                           (c*e+d*g)%modulus,(c*f+d*h)%modulus)
            e,f,g,h = ((e*e+f*g)%modulus,(e*f+f*h)%modulus,
                       (g*e+h*g)%modulus,(g*f+h*h)%modulus)
            n >>= 1
        return ((a,b),(c,d))
    assert raw_power(period)==((1,0),(0,1))
    assert raw_power(period//2)!=((1,0),(0,1))
    assert raw_power(period//3)!=((1,0),(0,1))
    assert phi_matrix(period,bits)==raw_power(period)
    assert phi_matrix(period//2,bits)!=((1,0),(0,1))
    assert phi_matrix(period//3,bits)!=((1,0),(0,1))
    assert FoldLedger(bits).stage(period*1000+42).materialize(words)==result
    # Independent sequential matrix application at the declared width.
    x,y = words[:2]
    for _ in range(42):
        x,y = (x+y)%modulus,x
    assert result[:2]==(x,y)


def test_native_operations_and_boundary():
    l = FoldLedger(8).stage(15)
    a,b = (1,3,200,255),(5,7,11,13)
    fa,fb = FoldedWords.from_plain(l,a),FoldedWords.from_plain(l,b)
    assert fa.add(fb)==FoldedWords.from_plain(l,tuple((x+y)%256 for x,y in zip(a,b)))
    assert fa.sub(fb)==FoldedWords.from_plain(l,tuple((x-y)%256 for x,y in zip(a,b)))
    assert fa.scale(-3)==FoldedWords.from_plain(l,tuple(-3*x%256 for x in a))
    assert fa.gram_dot(fb)==sum(x*y for x,y in zip(a,b))%256
    assert fa.equals(fa) and not fa.equals(fb)
    assert dedup((fa,fb,fa))==(fa,fb)
    assert keyed_lookup({fa:"a",fb:"b"},fb)=="b"
    assert fold_residency(("add","sort","equals"))==Fraction(2,3)
    assert not is_equivariant("zeckendorf_next")
    with pytest.raises(ValueError):
        fold_residency(())
    with pytest.raises(ValueError):
        is_equivariant("unknown")
    with pytest.raises(ValueError):
        fa.equals(FoldedWords.from_plain(FoldLedger(8),a))
    with pytest.raises(ValueError):
        l.materialize((256,0))


def test_compensating_edit_is_not_authentication():
    ledger = FoldLedger(8).stage(15)
    words = ledger.materialize((4,8))
    edited,detected = compensating_edit(words,(1,-1),8)
    assert not detected and edited!=words
    assert ledger.unfold(edited)!=(4,8)
    assert compensating_edit(words,(1,0),8)[1]
    with pytest.raises(ValueError):
        compensating_edit(words,(1,),8)


def test_sentinel_torus():
    cert=torus_certificate()
    assert cert["betti_q"]==cert["betti_f2"]==(1,2,1)
    assert (cert["n"],cert["k"],cert["d_z"],cert["d_x"],cert["distance"])==(21,2,3,6,3)


def test_capacity_address_and_computed_refusals():
    result=capacity_address(1000,warps_per_igpu=160)
    assert result["warps"]==160000
    from chronus.core.scaling import PVScale
    i=result["lucas_index"]
    assert PVScale(i-1).trace()<result["warps"]<=result["lucas_rung"]
    assert capacity_address(1001,warps_per_igpu=160)["within_tier_4_logical_warps"] is False
    assert refusal_registry()["gauss_p5"]["check"] and refusal_registry()["gauss_p7"]["check"]


def test_sentinel_content_only_digest():
    content={"modules":["units","ledger","codec","topology"]}
    a,b=seal(content,sealed_at="2026-11-19"),seal(content,sealed_at="2099-01-01")
    assert a["digest"]==b["digest"] and verify_seal(a) and verify_seal(b)
    assert not verify_seal(dict(a,digest="é"*64))
    assert not verify_seal(dict(a,digest="0"*63))
    content["modules"].append("new")
    assert verify_seal(a)
    a["content"]["modules"].append("tampered")
    assert not verify_seal(a)
    with pytest.raises(ValueError):
        seal({"unsupported":object()},sealed_at="x")


def test_findings_require_real_commit_and_evidence(tmp_path):
    def git(*args):
        return subprocess.check_output(["git","-C",str(tmp_path),*args]).decode().strip()
    git("init","-q")
    git("config","user.email","test@example.invalid")
    git("config","user.name","Closure test")
    data=b"independent test evidence"
    (tmp_path/"receipt.txt").write_bytes(data)
    git("add","receipt.txt")
    git("commit","-qm","receipt")
    sha=git("rev-parse","HEAD")
    item={"id":"F1","status":"CLOSED","commit":sha,"evidence_path":"receipt.txt",
          "evidence_sha256":hashlib.sha256(data).hexdigest()}
    assert validate_findings(tmp_path,[item],sha)==()
    assert validate_findings(tmp_path,[{"id":"F2","status":"OPEN"}],sha)==("F2",)
    with pytest.raises(ValueError):
        validate_findings(tmp_path,[dict(item,commit="0"*40)],sha)
    with pytest.raises(ValueError):
        validate_findings(tmp_path,[dict(item,evidence_sha256="0"*64)],sha)

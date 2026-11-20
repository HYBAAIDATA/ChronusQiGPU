"""Internal mathematical closure checks and content-only evidence envelopes.

Does not award release qualification. Findings are persisted as Git-tracked
records and closure requires a reachable commit and matching evidence bytes.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import subprocess
from math import isqrt
from pathlib import PurePosixPath

from chronus.fleet.canonical import canonical_json
from chronus.core.scaling import PVScale
from chronus.fleet.phase import TIER_4

_SHA = re.compile(r"[0-9a-f]{40}")
_DIGEST = re.compile(r"[0-9a-f]{64}")


def gauss_square_coefficients(p: int):
    """Compute the square in Z[zeta_p], reduce by 1+z+...+z^(p-1)."""
    if type(p) is not int or not 3 <= p <= 257 or p%2 == 0 or any(p%d == 0 for d in range(3,isqrt(p)+1,2)):
        raise ValueError("bounded odd prime required")
    counts = [0]*p
    for a in range(p):
        counts[a*a%p] += 1
    square = [0]*p
    for i,x in enumerate(counts):
        for j,y in enumerate(counts):
            square[(i+j)%p] += x*y
    return tuple(v-square[-1] for v in square[:-1])


def capacity_address(n_igpus: int, *, warps_per_igpu: int):
    """Logical design arithmetic, with an explicit unit; not fleet measurement."""
    if type(n_igpus) is not int or n_igpus < 0 or type(warps_per_igpu) is not int or warps_per_igpu <= 0:
        raise ValueError("nonnegative count and positive explicit unit required")
    warps = n_igpus*warps_per_igpu
    if not warps:
        return {"warps":0,"lucas_index":None,"lucas_rung":None}
    index = 1
    while PVScale(index).trace() < warps:
        index += 1
    return {"warps":warps,"lucas_index":index,"lucas_rung":PVScale(index).trace(),
            "within_tier_4_logical_warps":warps <= TIER_4.warps}


def refusal_registry():
    return {
        "gauss_p5":{"tier":1,"check":gauss_square_coefficients(5)==(5,0,0,0)},
        "gauss_p7":{"tier":1,"check":gauss_square_coefficients(7)==(-7,0,0,0,0,0)},
        "lift_zeta20":{"tier":2,"status":"separate TURING certificate required"},
        "pvnp":{"tier":3,"obstruction":"independent rung function and distillation lower bound",
                "retirement_test":"formal proof of separation"},
        "mass_gap":{"tier":3,"obstruction":"uniform control in volume and continuum limit",
                    "retirement_test":"constructive continuum theorem with uniform gap"},
        "eleven_d":{"tier":3,"obstruction":"nonperturbative model not established",
                    "retirement_test":"specified mathematical construction and proof"},
    }


def _exact_json(value):
    if value is None or type(value) in (str,int,bool):
        return
    if type(value) is list:
        for item in value:
            _exact_json(item)
        return
    if type(value) is dict and all(type(k) is str for k in value):
        for item in value.values():
            _exact_json(item)
        return
    raise ValueError("seal content must be exact JSON")


def seal(content: dict, *, sealed_at: str):
    if type(content) is not dict or type(sealed_at) is not str:
        raise ValueError("content object and explicit timestamp required")
    _exact_json(content)
    import json
    body = json.loads(canonical_json(content))
    return {"schema":"chronus.closure/1","content":body,"digest":hashlib.sha256(canonical_json(body)).hexdigest(),
            "sealed_at":sealed_at}


def verify_seal(envelope: dict) -> bool:
    if type(envelope) is not dict or set(envelope) != {"schema","content","digest","sealed_at"}:
        return False
    if envelope["schema"] != "chronus.closure/1" or type(envelope["digest"]) is not str or not _DIGEST.fullmatch(envelope["digest"]):
        return False
    try:
        expected = seal(envelope["content"],sealed_at=envelope["sealed_at"])
    except (ValueError,TypeError):
        return False
    return hmac.compare_digest(expected["digest"],envelope["digest"])


def _git(root,*args):
    return subprocess.check_output(["git","-C",str(root),*args],stderr=subprocess.PIPE)


def validate_findings(root, items, reviewed_sha):
    """Return open IDs; reject closure against unverified commit or evidence."""
    if not isinstance(reviewed_sha,str) or not _SHA.fullmatch(reviewed_sha):
        raise ValueError("full reviewed commit SHA required")
    try:
        _git(root,"cat-file","-e",reviewed_sha+"^{commit}")
    except subprocess.CalledProcessError as exc:
        raise ValueError("unavailable reviewed commit") from exc
    pending = []
    seen = set()
    for item in items:
        fid = item["id"]
        if type(fid) is not str or not fid or fid in seen:
            raise ValueError("invalid or duplicate finding identifier")
        seen.add(fid)
        status = item["status"]
        if status == "OPEN":
            pending.append(fid)
            continue
        if status != "CLOSED":
            raise ValueError("invalid finding status")
        sha,path,digest = (item["commit"],item["evidence_path"],item["evidence_sha256"])
        if not isinstance(sha,str) or not _SHA.fullmatch(sha) or not isinstance(digest,str) or not _DIGEST.fullmatch(digest):
            raise ValueError("closure requires full commit and evidence digest")
        if not isinstance(path,str) or not path or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
            raise ValueError("invalid evidence path")
        try:
            _git(root,"cat-file","-e",sha+"^{commit}")
            _git(root,"merge-base","--is-ancestor",sha,reviewed_sha)
            evidence = _git(root,"show",sha+":"+path)
        except subprocess.CalledProcessError as exc:
            raise ValueError("closure commit or evidence not attributable") from exc
        if not hmac.compare_digest(hashlib.sha256(evidence).hexdigest(),digest):
            raise ValueError("closure evidence mismatch")
    return tuple(pending)

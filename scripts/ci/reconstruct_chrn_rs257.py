"""Reconstruct the CHRN parameter-2 golden frame from the frozen specification.

Stdlib only, no Chronus imports. Author-run alternate implementation, not
non-author QC. Independent reviewers must derive their own output first.
"""
import argparse
import hashlib
import json
from math import comb
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "docs/storage/CHRN_RS257_PROFILE_RATIFICATION.md"
VECTOR = ROOT / "tests/vectors/chrn_rs257_v11.json"


def crc32c(raw):
    register = 0xffffffff
    for octet in raw:
        for bit in range(8):
            feedback = (register & 1) ^ ((octet >> bit) & 1)
            register >>= 1
            if feedback:
                register ^= 0x82f63b78
    return register ^ 0xffffffff


def parity(samples):
    # Newton forward difference interpolation at consecutive integer nodes.
    # P(1+t) = sum binom(t,j) Delta^j P(1), exactly modulo 257.
    row = samples[:]
    differences = []
    while row:
        differences.append(row[0])
        row = [(b-a) % 257 for a,b in zip(row,row[1:])]
    return [sum(comb(t,j)*d for j,d in enumerate(differences)) % 257
            for t in range(32,48)]


def reconstruct(source):
    fields = (256, 1, len(source), 256, 2)
    prefix = b"CHRN" + b"".join(v.to_bytes(w,"big") for v,w in zip(fields,(2,2,8,4,4)))
    prefix += hashlib.sha256(source).digest()
    result = bytearray(prefix + crc32c(prefix).to_bytes(4,"big"))
    for start in range(0,len(source),256):
        block=source[start:start+256]
        result.extend(block)
        lanes=[]
        for lane in range(8):
            data=[block[i] if i<len(block) else 0 for i in range(lane,256,8)]
            lanes.append(parity(data))
        for r in range(16):
            bits="".join(format(lanes[(i+len(block))%8][r],"09b") for i in range(8))
            result.extend(int(bits[i:i+8],2) for i in range(0,72,8))
    return bytes(result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    # Use input alone to construct candidate, only then consult expected bytes.
    vector=json.loads(VECTOR.read_text(encoding="utf-8"))
    source=bytes.fromhex(vector["input_hex"])
    actual=reconstruct(source)
    expected=bytes.fromhex(vector["expected_encoded_hex"])
    mismatches=sum(a!=b for a,b in zip(actual,expected))+abs(len(actual)-len(expected))
    digest=hashlib.sha256(actual).hexdigest()
    spec_digest=hashlib.sha256(SPEC.read_bytes()).hexdigest()
    passed=(mismatches==0 and digest==vector["expected_encoded_sha256"]
            and hashlib.sha256(source).hexdigest()==vector["input_sha256"])
    report={"source_commit":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
            "spec_sha256":spec_digest,"actual_sha256":digest,
            "expected_sha256":vector["expected_encoded_sha256"],"byte_mismatches":mismatches,
            "actual_bytes":len(actual),"expected_bytes":len(expected),"pass":passed,
            "method":"stdlib Newton forward differences; author-run alternate implementation",
            "independent_qc":"PENDING"}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,sort_keys=True))
    return 0 if passed else 1


if __name__=="__main__":
    raise SystemExit(main())

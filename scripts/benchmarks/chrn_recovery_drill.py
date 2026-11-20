"""Measure protected CHRN decode on deterministic, contiguous body-byte faults."""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from time import perf_counter_ns

from chronus.security.al_haras import reed_solomon as rs
from chronus.storage import chrn_frame as frame, chrn_rs257 as ecc

ROOT=Path(__file__).resolve().parents[2]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def source_block(seed: int):
    return b"".join(hashlib.sha256(seed.to_bytes(8,"big")+i.to_bytes(4,"big")).digest() for i in range(8))


def trial(source,wire,start,count,region):
    positions=range(frame.HEADER_SIZE+start,frame.HEADER_SIZE+start+count)
    damaged=rs.inject_faults(wire,positions)
    before=perf_counter_ns()
    try:
        result=ecc.decode_with_report(damaged)
    except frame.CorruptFrameError as exc:
        elapsed=perf_counter_ns()-before
        return {"region":region,"body_offset":start,"burst_bytes":count,"status":"rejected",
                "error":type(exc).__name__,"integrity_verified":False,"elapsed_ns":elapsed,
                "corrected_symbols":0,"corrected_byte_positions":[],
                "damaged_sha256":digest(damaged)}
    elapsed=perf_counter_ns()-before
    return {"region":region,"body_offset":start,"burst_bytes":count,"status":result.status,
            "integrity_verified":result.data==source,"elapsed_ns":elapsed,
            "corrected_symbols":len(result.corrected_symbols),
            "corrected_byte_positions":list(result.corrected_byte_positions),
            "damaged_sha256":digest(damaged)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed",type=int,default=19)
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args()
    if not 0<=args.seed<2**64:
        parser.error("seed outside uint64")
    def git(*argv):
        return subprocess.check_output(["git",*argv],cwd=ROOT).decode().strip()
    commit=git("rev-parse","HEAD")
    if git("status","--porcelain","--untracked-files=no"):
        raise SystemExit("tracked worktree is dirty")
    source=source_block(args.seed)
    wire=ecc.encode(source)
    started=utc()
    records=[]
    for burst in range(1,129):
        # Derive one START, not dispersed independent fault sites.
        start=int.from_bytes(hashlib.sha256(source+burst.to_bytes(2,"big")).digest()[:8],"big")%(256-burst+1)
        records.append(trial(source,wire,start,burst,"systematic"))
    for start in (224,256,336):
        records.append(trial(source,wire,start,64,"mixed" if start<256 else "parity"))
    records.append(trial(source,wire,200,65,"mixed"))
    records.append(trial(source,wire,256,72,"parity"))
    expected=[(r["status"]=="corrected" and r["integrity_verified"] and
               r["corrected_byte_positions"]==list(range(60+r["body_offset"],60+r["body_offset"]+r["burst_bytes"])))
              if r["burst_bytes"]<=64 or r["region"]!="systematic" else
              (r["status"]=="rejected" and not r["integrity_verified"]) for r in records]
    document={"schema":"chronus.chrn-rs257-recovery-drill/1",
              "source_commit":commit,"profile":"CHRN-RS257-INTERLEAVE","param_id":2,"seed":args.seed,
              "source_sha256":digest(source),"wire_sha256":digest(wire),"source_bytes":len(source),
              "encoded_body_bytes":len(wire)-60,"wire_bytes":len(wire),"started_utc":started,"ended_utc":utc(),
              "environment":{"platform":platform.platform(),"python":platform.python_version(),"machine":platform.machine(),
                             "processor":platform.processor()},
              "command":sys.argv,"working_directory":str(ROOT),
              "input_class":"deterministic software fault-injection fixture, not customer or device evidence",
              "trials":records,"all_expected_outcomes":all(expected),
              "exit_status":0 if all(expected) else 1}
    raw=json.dumps(document,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")+b"\n"
    sha=digest(raw)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    path=args.output_dir/f"chrn_recovery_{sha}.json"
    if path.exists() and path.read_bytes()!=raw:
        raise SystemExit("artifact collision")
    path.write_bytes(raw)
    print("CHRN_RECOVERY_SHA256="+sha)
    print("CHRN_RECOVERY_JSON="+raw.decode().rstrip("\n"))
    return document["exit_status"]


if __name__=="__main__":
    raise SystemExit(main())

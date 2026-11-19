#!/bin/bash
# Usage: pipeline.sh <sha> <run_dir> <outdir> <qv_dir>
set -e
SHA=$1; D=$2; O=$3; Q=$4; G=/workspace/closeout-data/gen
mkdir -p $O
python3 $G/make_extra.py pre $SHA $D $O/extra.json
python3 $G/fetch_closure.py 2026-11-19T01:00:00Z /workspace/closeout-data/closure.json
python3 - "$O/extra.json" <<'PY'
import json,sys; p=sys.argv[1]; d=json.load(open(p)); d["closure"]=json.load(open("/workspace/closeout-data/closure.json")); d["date"]="2026-11-19"; json.dump(d,open(p,"w"),indent=1)
PY
python3 $G/build_cfg.py $SHA $D $O $O/extra.json
python3 $G/gen.py $O/cfg.json
python3 $G/make_extra.py post $O/cfg.json $Q
python3 $G/render.py $O/cfg.json

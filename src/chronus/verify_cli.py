"""Independent evaluator CLI. Exit 0 valid, 2 invalid, 3 unavailable."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from chronus.chain import ChainBroken, verify_chain
from chronus.crypto.signers import SignerUnavailable

def main(argv: list[str] | None = None) -> int:
    p=argparse.ArgumentParser()
    p.add_argument("bundle",type=Path)
    p.add_argument("--inner-pk",required=True,type=Path)
    p.add_argument("--outer-pk",required=True,type=Path)
    a=p.parse_args(argv)
    try:
        paths=sorted(a.bundle.glob("*.json"))
        if not paths:
            raise ChainBroken("empty bundle")
        receipts=[json.loads(x.read_text(encoding="utf-8")) for x in paths]
        verify_chain(receipts,bytes.fromhex(a.inner_pk.read_text().strip()),bytes.fromhex(a.outer_pk.read_text().strip()))
    except SignerUnavailable as exc:
        print(json.dumps({"status":"UNQUALIFIED","detail":str(exc)}))
        return 3
    except (ChainBroken,ValueError,KeyError,TypeError,OSError) as exc:
        print(json.dumps({"status":"FAIL","detail":str(exc)}))
        return 2
    print(json.dumps({"status":"PASS","receipts":len(receipts)}))
    return 0

if __name__=="__main__":
    raise SystemExit(main())

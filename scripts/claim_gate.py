"""Block held claims in generated HTML. No site modification."""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

FOLD=str.maketrans({"–":"-","—":"-","−":"-","×":"x"})
def normalise(text:str)->str:
    return re.sub(r"\s+"," ",re.sub(r"<[^>]+>"," ",text).translate(FOLD).casefold()).strip()

def check(site:Path, register:Path)->list[str]:
    data=json.loads(register.read_text())
    html={str(p):normalise(p.read_text(errors="replace")) for p in site.rglob("*.html")}
    if not html:
        return ["site has no HTML; cannot qualify"]
    blocked=[]
    for claim in data["claims"]:
        if claim["state"]=="publishable" and not claim.get("gates"):
            blocked.append("unbacked publishable claim: "+claim["code"])
        if claim["state"]!="publishable":
            phrase=normalise(claim["text"])
            for page,text in html.items():
                if phrase and phrase in text:
                    blocked.append(claim["code"]+" appears in "+page)
    return blocked

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--check",type=Path,required=True)
    p.add_argument("--register",type=Path,default=Path("claims/register.json"))
    a=p.parse_args()
    try:
        blocked=check(a.check,a.register)
    except (OSError,ValueError,KeyError) as exc:
        blocked=[f"claim gate unavailable: {exc}"]
    for item in blocked:
        print("BLOCKED:",item)
    return 2 if blocked else 0
if __name__=="__main__":
    raise SystemExit(main())

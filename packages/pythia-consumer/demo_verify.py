"""60-second verification demo — genuine receipt, tamper, reject.

Runs against the source tree (no install needed) or an installed wheel:

    python demo_verify.py

Demonstrates the three trust levels: a genuine substrate-produced
certificate passes structural + canonical binding; a tampered token and
a tampered coordinate mask are each caught. Provenance authentication is
reported honestly as unsupported.
"""

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from pythia_consumer.verify import verify_receipt

FIXTURE = Path(__file__).parent / "tests" / "fixtures" / "zeckendorf_certificate.json"


def show(title, verdict):
    lvl = verdict["levels"]
    print(f"\n== {title}")
    print(f"   verdict:             {verdict['verdict']}")
    print(f"   structural:          {lvl['structural']}")
    print(f"   canonical_binding:   {lvl['canonical_binding']}")
    print(f"   provenance:          {lvl['provenance_authentication']}")
    failed = [c for c in verdict["checks"] if c["result"] == "fail"]
    for c in failed:
        print(f"   ✗ {c['check']}: {c['detail']}")


def main():
    receipt = json.loads(FIXTURE.read_text())
    print("PYTHIA verification demo — genuine producer receipt")
    print(f"receipt: {FIXTURE.name}  (toe.compute_zeckendorf_certificate output, verbatim)")

    show("genuine receipt", verify_receipt(receipt))

    tampered = copy.deepcopy(receipt)
    tampered["token_hex"] = "ZECK-" + "0" * 16
    show("tampered: token replaced", verify_receipt(tampered))

    tampered = copy.deepcopy(receipt)
    tampered["coordinate_masks"][0] ^= 0b100
    show("tampered: coordinate mask bit flipped", verify_receipt(tampered))

    print("\nThe token and canonical fold are re-derived independently —")
    print("changing any bound field breaks the receipt. Origin authenticity")
    print("requires a signature trust model, which is not yet implemented.")


if __name__ == "__main__":
    main()

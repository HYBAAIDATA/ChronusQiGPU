"""Reject overlapping install paths before co-installing selected product wheels.

This is an offline archive gate, not installed-runtime or release qualification.
Audit the complete candidate wheel set, including transitive HYBA dependencies.
"""
from __future__ import annotations

import argparse
import email
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile


def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def installed_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError(f"unsafe wheel path: {name!r}")
    parts = path.parts
    if not parts:
        raise ValueError("empty wheel path")
    if parts[0].endswith(".data"):
        if len(parts) < 3:
            raise ValueError(f"invalid wheel data path: {name!r}")
        # purelib and platlib land in the same import tree for this check.
        prefix = "site" if parts[1] in {"purelib", "platlib"} else parts[1]
        return prefix + "/" + "/".join(parts[2:])
    return "site/" + path.as_posix()


def audit(wheels):
    owners, products, records, errors = {}, set(), [], []
    for wheel in map(Path, wheels):
        with zipfile.ZipFile(wheel) as archive:
            names = [i.filename for i in archive.infolist() if not i.is_dir()]
            metadata = [n for n in names if n.endswith(".dist-info/METADATA")]
            if len(metadata) != 1:
                raise ValueError(f"{wheel.name}: expected one METADATA")
            message = email.message_from_bytes(archive.read(metadata[0]))
            if not message.get("Name") or not message.get("Version"):
                raise ValueError(f"{wheel.name}: missing distribution identity")
            product = normalize(message["Name"])
            if product in products:
                errors.append(f"multiple wheels for distribution: {product}")
            products.add(product)
            seen = set()
            for name in names:
                target = installed_path(name)
                if target in seen:
                    errors.append(f"duplicate member/install path in {wheel.name}: {target}")
                seen.add(target)
                owners.setdefault(target, []).append(wheel.name)
        records.append({"file": wheel.name, "product": product,
                        "version": message["Version"],
                        "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest()})
    singulars = {"hyba-kellogg-tensor", "hyba-turing-vqc", "hyba-chronus-igpu",
                 "hyba-chronos-mathematics", "hyba-chronos-one-igpu",
                 "hyba-theseus-storage", "hyba-ovid-data-organisation"}
    if "hyba-pythia-consumer" in products and products & singulars:
        errors.append("consumer bundle must not co-install with singular product wheels")
    collisions = {p: o for p, o in sorted(owners.items()) if len(o) > 1}
    if collisions:
        errors.append("multiple wheel owners for installed paths")
    return {"scope": "OFFLINE_WHEEL_OWNERSHIP_ONLY", "status": "FAIL" if errors else "PASS",
            "wheels": records, "collisions": collisions, "errors": errors,
            "release_qualification": "NOT_EVALUATED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheels", type=Path, nargs="+")
    args = parser.parse_args()
    try:
        report = audit(args.wheels)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return int(report["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())

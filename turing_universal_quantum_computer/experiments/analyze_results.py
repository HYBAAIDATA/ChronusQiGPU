"""Validate experiment manifests and regenerate row-level CSV/TeX, without edited cells."""

from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def validate_manifest(path):
    data = json.loads(Path(path).read_text())
    declared = data.pop("manifest_digest", None)
    if data.get("schema") != "turing.experiment_manifest.v1" or declared != digest(data):
        raise ValueError("Unsupported or modified manifest")
    if data.get("status") != "completed" or data.get("configuration_hash") != digest(
        data.get("configuration")
    ):
        raise ValueError("Incomplete experiment or configuration mismatch")
    config = data["configuration"]
    references = {
        "bell_z0": ["0", "0"],
        "radical_z0": ["0", "1/2"],
        "finite_variational_z0": ["-1", "0"],
    }
    if not config["cases"] or any(case not in references for case in config["cases"]):
        raise ValueError("Unknown case/reference")
    if type(config["repetitions"]) is not int or not 1 <= config["repetitions"] <= 100:
        raise ValueError("Invalid repetitions")
    measurements = data["measurements"]
    expected = {
        (case, repetition)
        for case in config["cases"]
        for repetition in range(config["repetitions"])
    }
    if (
        len(measurements) != len(expected)
        or {(m["case"], m["repetition"]) for m in measurements} != expected
    ):
        raise ValueError("Incomplete/duplicate experimental coverage")
    for m in measurements:
        if m["exact_coefficients"] != references[m["case"]]:
            raise ValueError("Independent analytic reference mismatch")
        if (
            m["verified"] is not True
            or m["exact_coefficients"] != m["reference_coefficients"]
            or m["shots"] is not None
        ):
            raise ValueError("Reference or analytic execution mismatch")
        if not m["jobs"] or m["evaluations"] != len(m["jobs"]):
            raise ValueError("Missing evaluation evidence")
        for job in m["jobs"]:
            envelope = job["evidence"]
            report = envelope["pipeline_report"]
            if (
                report["verdict"] != "PASS"
                or not report["certificate"]
                or not report["witness"]
                or job["request_hash"] != envelope["request_hash"]
            ):
                raise ValueError("Missing/mismatched canonical evidence")
    data["manifest_digest"] = declared
    return data


def generate(manifest, output):
    data = validate_manifest(manifest)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for measurement in sorted(data["measurements"], key=lambda m: (m["case"], m["repetition"])):
        rows.append(
            {
                "run_id": data["run_id"],
                "case": measurement["case"],
                "repetition": measurement["repetition"],
                "rational": measurement["exact_coefficients"][0],
                "sqrt2": measurement["exact_coefficients"][1],
                "value": measurement["value"],
                "evaluations": measurement["evaluations"],
                "wall_time_ns": measurement["wall_time_ns"],
                "source_state": data["source"]["state"],
                "qualification": data["qualification"],
            }
        )
    csv_path = output / "exact_package_validation.csv"
    with csv_path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    tex_path = output / "exact_package_validation.tex"
    lines = [
        "% Generated from validated manifest " + data["manifest_digest"],
        "% Qualification: " + data["qualification"],
        r"\begin{tabular}{lrrrr}",
        r"Case & Repetition & Rational & $\sqrt{2}$ coefficient & Evaluations \\",
        r"\hline",
    ]
    for row in rows:
        case = row["case"].replace("_", r"\_")
        lines.append(
            f"{case} & {row['repetition']} & {row['rational']} & {row['sqrt2']} & {row['evaluations']} "
            + r"\\"
        )
    lines.append(r"\end{tabular}")
    tex_path.write_text("\n".join(lines) + "\n")
    return csv_path, tex_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for path in generate(args.manifest, args.output):
        print(path)

"""Physical evidence gate for the Intel UHD 620 Chronus OpenCL tensor path.

Thin wrapper. The gate itself is :class:`chronus.conformance.OpenCLConformanceSuite`
so that the same suite — same identity negative, same certified operations, same
non-tile-aligned boundary shapes, same tolerance — gates any OpenCL device
Chronus is asked to trust, including a Chronus-provided one.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DEFAULT_DEVICE = "UHD Graphics 620"

#: Findings the earlier UHD 620 run raised, now closed in the repository.
RESOLVED_FINDINGS = (
    {
        "id": "HYBA_DEVICE_ALIAS-fatal-without-HYBA",
        "severity": "low",
        "disposition": "fixed",
        "detail": (
            "An alias that resolves to no catalog family is fatal only under "
            "HYBA_REQUIRE_HYBA=1 (hyba.device.resolve_alias raises "
            "AliasUnresolvedError). With HYBA_REQUIRE_HYBA=0 the alias ranks "
            "candidates and an explicit CHRONUS_OPENCL_DEVICE remains the "
            "fail-closed identity."
        ),
    },
    {
        "id": "generic-graphics-match",
        "severity": "low",
        "disposition": "fixed",
        "detail": (
            "hyba.catalog.find_spec scores evidence (PCI env, PCI in name, "
            "longest name alias, generic alias, vendor alone) and generic vendor "
            "entries can only be reached on the weakest evidence. An unlisted "
            "Intel GPU now reports intel-generic with known=false instead of "
            "being filed under intel-uhd-620."
        ),
    },
    {
        "id": "matmul-wg-planning",
        "severity": "low",
        "disposition": "fixed",
        "detail": (
            "chronus.tensor_compute.plan_work_group returns "
            "min(CL_DEVICE_MAX_WORK_GROUP_SIZE, CL_KERNEL_WORK_GROUP_SIZE) and "
            "every launch is planned from it; the ceiling is recorded in each "
            "execution evidence record and asserted by the work_group_planning "
            "gate check."
        ),
    },
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--device", default=DEFAULT_DEVICE, help="required device identity")
    parser.add_argument("--platform", default="", help="optional OpenCL platform filter")
    parser.add_argument("--vendor", default="Intel", help="required device vendor")
    parser.add_argument("--alias", default="intel,uhd", help="HYBA alias preference list")
    parser.add_argument(
        "--require-hyba",
        default="0",
        choices=("0", "1"),
        help="1 makes an unresolved alias fatal instead of advisory",
    )
    parser.add_argument(
        "--artifacts",
        default=os.path.join("artifacts", "intel-uhd-620"),
        help="directory for the evidence set",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    os.environ.setdefault("HYBA_REQUIRE_HYBA", "0")
    os.environ["HYBA_DEVICE_VENDOR"] = args.vendor
    os.environ["HYBA_DEVICE_ALIAS"] = args.alias
    os.environ["HYBA_REQUIRE_HYBA"] = args.require_hyba
    os.environ["CHRONUS_OPENCL_DEVICE"] = args.device
    if args.platform:
        os.environ["CHRONUS_OPENCL_PLATFORM"] = args.platform

    from chronus.conformance import OpenCLConformanceSuite

    suite = OpenCLConformanceSuite(
        target="intel-uhd-620",
        artifact_dir=args.artifacts,
        findings=RESOLVED_FINDINGS,
    )
    result = suite.run()

    for check in result.checks:
        print(f"{check.status:4s}  {check.name:22s}  {check.detail}")
    print(f"\nstatus: {result.status}")
    print(f"evidence: {result.artifact_dir}")
    print(f"hash chain: {result.hash_chain}")
    if result.failures:
        print(json.dumps({"failures": list(result.failures)}, indent=2))
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())

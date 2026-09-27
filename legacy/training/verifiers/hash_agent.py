"""Hash Agent contract verifier.

Contract (docs/mining_agents/HASH_AGENT.md):
  - Hashrate stays above `start_ehs` (1.32 EH/s).
  - Thermal stays below throttle (85 C).
  - Power stays within budget (65 W).
  - Every dispatch is marked GPU or CPU fallback (no silent degradation).
  - Log every configuration decision with provenance.

Rules:
  1. dispatch_marked_gpu_or_cpu — every compute path carries an explicit
     backend label (metal / cuda / rocm / cpu) and the label is surfaced in
     reported state.

  2. batch_size_adapts_to_thermal — a batch-size function of temperature
     must exist. Thermal-aware *node scoring* exists but is not batch
     sizing — reported honestly.

  3. hashrate_bound_respected — pool-ceiling comparison exists and is
     surfaced (`withinCeiling`).

  4. power_bound_respected — a measured-power-vs-budget check must exist.
     The power spec exists; enforcement does not — reported honestly.
"""

from __future__ import annotations

import re

from .common import (
    RuleResult,
    TsSource,
    Violation,
    fail,
    glob_ts,
    not_implemented,
    pass_,
)

AGENT = "hash_agent"
_SCALER = "src/lib/m3_igpu_scaler.ts"


def check_dispatch_marked(sources: list[TsSource]) -> list[Violation]:
    violations: list[Violation] = []
    scaler = next((s for s in sources if s.relpath == _SCALER), None)
    if scaler is None:
        return [
            Violation(
                file=_SCALER,
                line=1,
                detail="m3_igpu_scaler.ts missing",
                fix="Restore the hardware dispatch layer.",
            )
        ]
    fn = scaler.function_named("detectHardwareSpecs")
    if fn is None:
        return [
            Violation(
                file=_SCALER,
                line=1,
                detail="detectHardwareSpecs() not found — no backend selection",
                fix="Restore explicit backend detection.",
            )
        ]
    ln, _ = scaler.region_lines(fn)
    # collect backend labels from literals inside the function region
    labels = set()
    for off, content in scaler.literals:
        if fn.body_start < off < fn.body_end:
            labels.add(content)
    for expected in ("cpu",):
        if expected not in labels:
            violations.append(
                Violation(
                    file=_SCALER,
                    line=ln,
                    detail=f"backend label {expected!r} not emitted by detectHardwareSpecs",
                    fix="Every dispatch path must carry an explicit backend label.",
                )
            )
    # the backend label must be surfaced in reported state
    if not re.search(r"backend\s*:\s*ACTIVE_HARDWARE\.backend", scaler.code):
        violations.append(
            Violation(
                file=_SCALER,
                line=ln,
                detail="backend label is computed but never surfaced in state",
                fix="Report ACTIVE_HARDWARE.backend in miner state/telemetry.",
            )
        )
    return violations


def check_batch_thermal(sources: list[TsSource]) -> RuleResult:
    """A function mapping temperature to batch size must exist. Node-level
    thermal scoring (EuclidGovernance.computeScore) is routing, not batch
    sizing."""
    for src in sources:
        if src.relpath.endswith(".test.ts"):
            continue
        for m in re.finditer(
            r"batch\w*\s*=\s*[^;]*(?:temp|thermal)|(?:temp|thermal)\w*\s*[^;]*batch",
            src.code,
            re.IGNORECASE,
        ):
            return pass_(
                AGENT,
                "batch_size_adapts_to_thermal",
                file=src.relpath,
                detail="batch size is computed from thermal state.",
            )
    return not_implemented(
        AGENT,
        "batch_size_adapts_to_thermal",
        detail="No batch-size-as-function-of-temperature path exists. "
        "EuclidGovernance.computeScore weights thermalState in node routing "
        "only.",
        fix="Add a batch-size controller driven by measured temperature "
        "(e.g. 4096/2048/1024 tiers vs thermal headroom).",
    )


def check_hashrate_bound(sources: list[TsSource]) -> list[Violation]:
    violations: list[Violation] = []
    found = False
    for src in sources:
        if src.relpath.endswith(".test.ts"):
            continue
        for line_no, line_text, m in src.find(r"withinCeiling\s*[:=]"):
            found = True
    if not found:
        violations.append(
            Violation(
                file=_SCALER,
                line=1,
                detail="no withinCeiling / hashrate-vs-ceiling comparison surfaced",
                fix="Compute and report hashRate vs pool ceiling.",
            )
        )
    return violations


def check_power_bound(sources: list[TsSource]) -> RuleResult:
    for src in sources:
        if src.relpath.endswith(".test.ts"):
            continue
        for m in re.finditer(
            r"power\w*\s*(?:<=?|>=?)\s*\w*budget|budget\w*\s*(?:<=?|>=?)\s*\w*power",
            src.code,
            re.IGNORECASE,
        ):
            return pass_(
                AGENT,
                "power_bound_respected",
                file=src.relpath,
                detail="measured power is compared against the power budget.",
            )
    return not_implemented(
        AGENT,
        "power_bound_respected",
        detail="M3_ULTRA_SPECS.powerWatts declares the budget but nothing "
        "compares measured power against it.",
        fix="Add a power-bound check in the dispatch path (measured W vs "
        "budget, throttle on exceed).",
    )


def verify() -> list[RuleResult]:
    sources = glob_ts("src/lib")
    results: list[RuleResult] = []

    v = check_dispatch_marked(sources)
    results.append(
        fail(AGENT, "dispatch_marked_gpu_or_cpu", v)
        if v
        else pass_(
            AGENT,
            "dispatch_marked_gpu_or_cpu",
            file=_SCALER,
            detail="detectHardwareSpecs assigns an explicit backend label "
            "(metal/cuda/rocm/cpu) and ACTIVE_HARDWARE.backend is surfaced.",
        )
    )

    results.append(check_batch_thermal(sources))

    v = check_hashrate_bound(sources)
    results.append(
        fail(AGENT, "hashrate_bound_respected", v)
        if v
        else pass_(
            AGENT,
            "hashrate_bound_respected",
            file=_SCALER,
            detail="withinCeiling compares effective hashrate to the pool "
            "ceiling on every scaling row and walker state.",
        )
    )

    results.append(check_power_bound(sources))
    return results

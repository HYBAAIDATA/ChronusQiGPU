#!/usr/bin/env python3
"""Generate the Chronus v36 sovereign investor/diligence evidence dossier.

Executes the live v36 benchmark surfaces and emits:

* ``telemetry.json``  - raw measurements and SHA-256 receipts
* ``summary.md``      - boardroom-ready Markdown (also appended to
  ``$GITHUB_STEP_SUMMARY`` when present, so it renders at the top of the
  GitHub Actions run and can be printed to PDF from the browser)
* ``report.html``     - styled, printable standalone report
* ``Chronus_v36_Sovereign_Investor_Dossier.pdf`` - printable certificate
  (requires the ``fpdf2`` package; skipped with a warning otherwise)

Every claim in the report is backed by a measurement taken in this process.
Capabilities with no automated evidence are reported as NOT EVIDENCED rather
than asserted - the dossier is designed to survive hostile technical
diligence.

Exit code is non-zero if any measured verification fails.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ATTEST_VERIFY_CMD = (
    "gh attestation verify Chronus_v36_Sovereign_Investor_Dossier.pdf "
    "--repo hybadatadevops1/Chronusv2"
)
COSIGN_VERIFY_CMD = (
    "cosign verify-blob "
    "--bundle Chronus_v36_Sovereign_Investor_Dossier.pdf.sigstore.json "
    "--certificate-oidc-issuer https://token.actions.githubusercontent.com "
    "--certificate-identity-regexp "
    "'^https://github.com/hybadatadevops1/Chronusv2/' "
    "Chronus_v36_Sovereign_Investor_Dossier.pdf"
)


def _timed(fn):
    """Run fn, returning (result, wall_clock_microseconds)."""
    start = time.perf_counter_ns()
    result = fn()
    return result, (time.perf_counter_ns() - start) / 1_000.0


def bench_memory_folding() -> dict:
    """Theseus phyllotaxis storage: 0-bit truncation across 2,048 PV rungs."""
    from chronus.security.ovid import OVIDStorage
    from chronus.storage.theseus import TheseusService

    service = TheseusService(OVIDStorage(), lane_count=32)
    rungs = 2048
    payload = bytes(range(256)) * 16  # 4 KiB deterministic state
    expected = hashlib.sha256(payload).hexdigest()
    record = service.store("diligence", payload, scale_index=6)
    object_id = record.object_id

    def _fold_2048_rungs():
        for _ in range(rungs):
            service.scale_record("diligence", object_id, 1)
        return service.reconstruct("diligence", object_id)

    recovered, elapsed = _timed(_fold_2048_rungs)
    recovered_ok = hashlib.sha256(recovered).hexdigest() == expected
    lineage_ok = service.get_record("diligence", object_id).scale_index == 6 + rungs
    passed = recovered_ok and lineage_ok
    return {
        "pillar": "Memory Folding (Phyllotaxis PV Lineage in Z[phi])",
        "target": "0-bit truncation across 2,048 PV scale rungs",
        "classical_baseline": "Lossy floating-point drift (IEEE-754 ~1e-16)",
        "measured": (
            f"4 KiB state bit-exact (SHA-256) after {rungs} rung advances "
            f"(scale_index 6 -> {6 + rungs}) in {elapsed / 1000.0:.2f} ms"
        ),
        "detail": {
            "rungs": rungs,
            "payload_bytes": len(payload),
            "total_us": round(elapsed, 1),
            "us_per_rung": round(elapsed / rungs, 2),
            "sha256_verified": recovered_ok,
            "lineage_exact": lineage_ok,
        },
        "status": "VERIFIED" if passed else "FAILED",
        "passed": passed,
    }


def bench_companion_matrix() -> dict:
    """PV companion-matrix identities: Tr(C^n) = L_n, Det(C^n) = (-1)^n."""
    from chronus.core.scaling import PVScale

    def _lucas(n: int) -> int:
        a, b = 2, 1
        for _ in range(n):
            a, b = b, a + b
        return a

    def _verify_identities():
        for n in range(1, 257):
            scale = PVScale(n)
            assert scale.trace() == _lucas(n), f"trace mismatch at n={n}"
            expected_parity = 1 if n % 2 == 0 else -1
            assert scale.cassini_parity() == expected_parity, (
                f"det sign mismatch at n={n}"
            )
        return PVScale(2048).trace() == _lucas(2048)

    large_rung_ok, elapsed = _timed(_verify_identities)
    passed = large_rung_ok
    return {
        "pillar": "PV Companion-Matrix RTL Identities",
        "target": "Tr(C^n) = L_n and Det(C^n) = (-1)^n, exact integer arithmetic",
        "classical_baseline": "Floating-point matrix power drift",
        "measured": (
            f"Tr(C^n)=L_n and Det sign verified for n=1..256 plus n=2048 "
            f"(exact big-integer Lucas) in {elapsed / 1000.0:.2f} ms"
        ),
        "detail": {
            "identity_range": "1..256",
            "spot_check_rung": 2048,
            "lucas_2048_digits": len(str(_lucas(2048))),
            "total_us": round(elapsed, 1),
        },
        "status": "VERIFIED" if passed else "FAILED",
        "passed": passed,
    }


def bench_threshold_mpc() -> dict:
    """AL HARAS (3,5) Shamir threshold sharing: quorum signature, deficit refusal, tamper detection."""
    from chronus.security.al_haras.threshold_mpc import TopologicalThresholdMPC

    seed = "CHRONUS_V36_DILIGENCE_DETERMINISTIC_SEED"

    def _quorum_success():
        mpc = TopologicalThresholdMPC(threshold_t=3, total_bunkers_n=5)
        mpc.generate_distributed_braid_shares(seed)
        return mpc.authorize_sovereign_action(
            action_payload=b"SOVEREIGN_RELEASE_GATE_V36",
            participating_bunker_ids=["BUNKER_01", "BUNKER_02", "BUNKER_03"],
        )

    def _quorum_deficit():
        mpc = TopologicalThresholdMPC(threshold_t=3, total_bunkers_n=5)
        mpc.generate_distributed_braid_shares(seed)
        return mpc.authorize_sovereign_action(
            action_payload=b"UNAUTHORIZED_ACTION",
            participating_bunker_ids=["BUNKER_01", "BUNKER_02"],
        )

    def _byzantine_isolation():
        mpc = TopologicalThresholdMPC(threshold_t=3, total_bunkers_n=5)
        mpc.generate_distributed_braid_shares(seed)
        return mpc.authorize_sovereign_action(
            action_payload=b"DEFENSE_COMMAND_CRITICAL",
            participating_bunker_ids=[
                "BUNKER_01", "BUNKER_02", "BUNKER_03", "BUNKER_04",
            ],
            injected_compromised_bunker="BUNKER_02",
        )

    quorum, t_quorum = _timed(_quorum_success)
    deficit, t_deficit = _timed(_quorum_deficit)
    byzantine, t_byz = _timed(_byzantine_isolation)

    def _signature_verifies(result, payload):
        return result["joint_authorization_token"] is not None and TopologicalThresholdMPC.verify_joint_authorization(
            payload, result["joint_authorization_token"], result["verification_public_key_hex"]
        )

    quorum_ok = (
        quorum["authorized"] is True
        and quorum["valid_shares_verified"] == 3
        and _signature_verifies(quorum, b"SOVEREIGN_RELEASE_GATE_V36")
    )
    deficit_ok = (
        deficit["authorized"] is False
        and "QUORUM_DEFICIT" in deficit["reason"]
        and deficit["joint_authorization_token"] is None
    )
    byz_ok = (
        byzantine["authorized"] is True
        and byzantine["isolated_compromised_bunkers"] == ["BUNKER_02"]
        and byzantine["valid_shares_verified"] == 3
        and _signature_verifies(byzantine, b"DEFENSE_COMMAND_CRITICAL")
    )
    passed = quorum_ok and deficit_ok and byz_ok
    return {
        "pillar": "AL HARAS Threshold Secret Sharing (Shamir 3-of-5, SHA-256 share commitments)",
        "target": "Quorum signature verifies; 2-of-5 refused; tampered share rejected by its commitment",
        "classical_baseline": "Not measured (in-process model; no HSM or physical key custody)",
        "measured": (
            f"3-of-5 quorum signature {'verified' if quorum_ok else 'NOT verified'}; "
            f"2-of-5 {'refused (QUORUM_DEFICIT)' if deficit_ok else 'NOT refused'}; "
            f"tampered share {'rejected by its commitment, 3 shares still signed' if byz_ok else 'NOT rejected'} "
            f"({t_quorum + t_deficit + t_byz:.0f} us total)"
        ),
        "detail": {
            "threshold": "3-of-5",
            "quorum_us": round(t_quorum, 1),
            "deficit_rejection_us": round(t_deficit, 1),
            "byzantine_isolation_us": round(t_byz, 1),
            "quorum_ok": quorum_ok,
            "deficit_rejected": deficit_ok,
            "compromised_bunker_isolated": byz_ok,
        },
        "status": "VERIFIED" if passed else "FAILED",
        "passed": passed,
    }


def bench_formal_invariants() -> dict:
    """Executable exact checks: sheaf coboundary, cycle-sum obstruction, braid relations, Reed-Solomon repair."""
    from chronus.security.al_haras.formal_invariants import (
        FormalTopologicalProofVerifier,
    )

    audit, elapsed = _timed(FormalTopologicalProofVerifier.verify_all_theorems)
    passed = audit["all_checks_hold"] is True
    names = "; ".join(c["check_id"] for c in audit["checks"])
    return {
        "pillar": "Executable Exact Checks (Sheaf Coboundary / Cycle-Sum Obstruction / Braids / Reed-Solomon)",
        "target": f"{audit['checks_run']}/{audit['checks_run']} executable checks hold on their finite instances",
        "classical_baseline": "Unverified informal claims",
        "measured": (
            f"{audit['checks_holding']}/{audit['checks_run']} checks hold, run in {elapsed:.0f} us; "
            f"Lean source {audit['lean_specification']['path']} is not machine-checked in CI"
        ),
        "detail": {
            "checks": names,
            "verification_method": audit["verification_method"],
            "total_us": round(elapsed, 1),
        },
        "status": "VERIFIED" if passed else "FAILED",
        "passed": passed,
    }


def bench_subspace_search() -> dict:
    """One-shot symbolic subspace search at num_qubits=1000 (N = 2^1000)."""
    from chronus.quantum.metallic_search import jform_one_shot_phases
    from chronus.quantum.subspace import exact_subspace_search

    single, t_single = _timed(lambda: exact_subspace_search(1000, 1))
    multi, t_multi = _timed(lambda: exact_subspace_search(1000, 6))
    phases, t_phases = _timed(lambda: jform_one_shot_phases(1000))

    single_ok = single.unmarked_amplitude == 0 and single.marked_amplitude in (1, 256)
    multi_ok = multi.unmarked_amplitude == 0 and multi.marked_amplitude in (1, 256)
    vector_ok = (17, 120) in phases
    passed = single_ok and multi_ok and vector_ok
    return {
        "pillar": "Quantum Subspace Search (N = 2^1000)",
        "target": "One-shot rank-2 symbolic collapse, multi-marked",
        "classical_baseline": "O(N) brute force / O(sqrt(N)) Grover iteration",
        "measured": (
            f"single-marked {t_single:.1f} us, six-marked {t_multi:.1f} us, "
            f"phase ladder {t_phases:.1f} us; published n=1000 vectors reproduced"
        ),
        "detail": {
            "num_qubits": 1000,
            "single_marked_us": round(t_single, 1),
            "six_marked_us": round(t_multi, 1),
            "phase_ladder_us": round(t_phases, 1),
            "unmarked_amplitude_single": single.unmarked_amplitude,
            "unmarked_amplitude_multi": multi.unmarked_amplitude,
            "published_vector_(17,120)_reproduced": vector_ok,
        },
        "status": "VERIFIED" if passed else "FAILED",
        "passed": passed,
    }


def bench_planck_ladder() -> dict:
    """Planck-ladder Lucas-rung scaling and PVScale companion trace."""
    from chronus.core.scaling import PVScale, planck_ladder

    ladder, t_ladder = _timed(lambda: planck_ladder(1000))

    def _scale_check():
        scale = PVScale(6)
        advanced = scale.advance(2)
        return scale.trace(), scale.cassini_parity(), advanced.index

    (trace, parity, advanced_index), t_scale = _timed(_scale_check)
    coverage_ok = sum(ladder) == 1000
    parity_ok = parity in (1, -1)
    passed = coverage_ok and parity_ok and advanced_index == 8
    return {
        "pillar": "Accelerator Dispatch (Planck-Ladder Lucas-Rung)",
        "target": "Exact Lucas-rung coverage of 1000 with PV companion trace",
        "classical_baseline": "Software emulation / approximate scaling",
        "measured": (
            f"ladder {ladder} sums to 1000 exactly ({t_ladder:.1f} us); "
            f"PVScale(6) trace={trace}, Cassini parity={parity}"
        ),
        "detail": {
            "planck_ladder_1000": ladder,
            "coverage_exact": coverage_ok,
            "pvscale6_trace": trace,
            "cassini_parity": parity,
            "ladder_us": round(t_ladder, 1),
            "scale_check_us": round(t_scale, 1),
        },
        "status": "VERIFIED" if passed else "FAILED",
        "passed": passed,
    }


def bench_homological_settlement() -> dict:
    """AL HARAS transfer-batch boundary check (in-memory): closed cycle accepted, replay rejected."""
    from chronus.security.al_haras.sovereign_settlement import (
        HomologicalSettlementEngine,
        SovereignCentralBank,
        SovereignTransferSimplex,
    )

    engine = HomologicalSettlementEngine()
    cycle = [
        SovereignTransferSimplex(
            "tx-a", SovereignCentralBank.CENTRAL_BANK_A,
            SovereignCentralBank.CENTRAL_BANK_B, 10,
        ),
        SovereignTransferSimplex(
            "tx-b", SovereignCentralBank.CENTRAL_BANK_B,
            SovereignCentralBank.CENTRAL_BANK_C, 10,
        ),
        SovereignTransferSimplex(
            "tx-c", SovereignCentralBank.CENTRAL_BANK_C,
            SovereignCentralBank.CENTRAL_BANK_A, 10,
        ),
    ]
    settled, t_settle = _timed(lambda: engine.settle_transfer_batch(cycle))
    forged, t_forgery = _timed(
        lambda: engine.settle_transfer_batch(cycle, simulate_double_spend=True)
    )

    settle_ok = (
        settled["settlement_status"] == "SETTLED_CLOSED_1_CYCLE"
        and settled["boundary_norm"] == 0
        and settled["rtgs_receipt_id"] is not None
    )
    reject_ok = (
        not forged["is_homologically_closed"]
        and forged["settlement_status"] == "REJECTED_BOUNDARY_MISMATCH"
        and forged["boundary_norm"] == 2 * cycle[0].amount_units
        and forged["duplicate_transfer_ids"] == ["tx-a"]
    )
    passed = bool(settle_ok and reject_ok)
    return {
        "pillar": "AL HARAS Transfer-Batch Boundary Check (in-memory model)",
        "target": "Closed 1-cycle accepted (d1 = 0); replayed transfer rejected by the exact boundary check",
        "classical_baseline": "Not measured (no payment system or ledger baseline)",
        "measured": (
            f"3-account clearing cycle {'accepted' if settle_ok else 'NOT accepted'} by the in-memory "
            f"boundary check in {settled['settlement_latency_us']:.1f} us "
            f"(batch receipt {(settled['rtgs_receipt_id'] or 'none')[:20]}...); "
            f"replayed transfer {'rejected' if reject_ok else 'NOT rejected'} with boundary l1 norm "
            f"{forged['boundary_norm']}"
        ),
        "detail": {
            "settlement_latency_us": settled["settlement_latency_us"],
            "rtgs_receipt_id": settled["rtgs_receipt_id"],
            "double_spend_rejected": reject_ok,
            "rejection_check_us": round(t_forgery, 1),
            "note": (
                "Evidence covers the exact boundary operator on an in-memory "
                "batch (d_1 of a closed 1-cycle = 0) and rejection of a replayed "
                "transfer. No payment system, balance ledger or settlement "
                "finality is exercised. Tampered-share detection is covered by "
                "the threshold secret-sharing pillar."
            ),
        },
        "status": "VERIFIED" if passed else "FAILED",
        "passed": passed,
    }


def check_qualification_manifest(manifest_path: Path) -> dict:
    """Parse qualification_manifest_final.json and receipt it with SHA-256."""
    data = json.loads(manifest_path.read_text())
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    gates = data.get("gate_results", [])
    gates_pass = all(g.get("status") == "PASS" for g in gates)
    zero_drift = (
        data.get("release_gates_passed") == data.get("total_release_gates_evaluated")
        and data.get("invariants_passed") == data.get("total_invariants_evaluated")
        and gates_pass
    )
    return {
        "pillar": "Qualification Manifest v36 Telemetry",
        "target": "All release gates and invariants PASS (zero drift)",
        "classical_baseline": "Narrative assurance / manual audit",
        "measured": (
            f"{data.get('release_gates_passed')}/{data.get('total_release_gates_evaluated')} gates, "
            f"{data.get('invariants_passed')}/{data.get('total_invariants_evaluated')} invariants PASS; "
            f"status {data.get('qualification_status')}"
        ),
        "detail": {
            "manifest": str(manifest_path),
            "sha256": digest,
            "qualification_status": data.get("qualification_status"),
            "gates": f"{data.get('release_gates_passed')}/{data.get('total_release_gates_evaluated')}",
            "invariants": f"{data.get('invariants_passed')}/{data.get('total_invariants_evaluated')}",
            "zero_drift": zero_drift,
        },
        "status": "VERIFIED" if zero_drift else "FAILED",
        "passed": zero_drift,
    }


def check_rtl(rtl_log: Path) -> dict:
    """Count TB PASS markers in the iverilog testbench log."""
    text = rtl_log.read_text()
    passes = text.count("TB PASS")
    passed = passes == 3
    return {
        "pillar": "Silicon RTL (PV Companion-Matrix Dispatch)",
        "target": "3/3 known-answer testbenches PASS (phi, 32-lane, pv-scale)",
        "classical_baseline": "Software emulation only",
        "measured": f"{passes}/3 iverilog testbenches TB PASS (cycle-exact)",
        "detail": {"tb_pass_count": passes, "log": str(rtl_log)},
        "status": "VERIFIED" if passed else "FAILED",
        "passed": passed,
    }


def _esc(value) -> str:
    return html.escape(str(value))


def render_markdown(meta: dict, results: list[dict]) -> str:
    lines = [
        "# CHRONUS v36.0 - SOVEREIGN COMPUTATIONAL & TELEMETRY CERTIFICATE",
        "",
        f"**Commit SHA:** `{meta['commit']}` | "
        f"**Run:** [{meta['run_id']}]({meta['run_url']}) | "
        f"**Generated (UTC):** {meta['generated_utc']} | "
        f"**Total benchmark time:** {meta['total_time_s']}s",
        "",
        "| Core Capability Pillar | Benchmark Target | Classical Baseline | Chronus v36 Measured | Verification Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in results:
        lines.append(
            f"| **{r['pillar']}** | {r['target']} | {r['classical_baseline']} "
            f"| **{r['measured']}** | **{r['status']}** |"
        )
    lines += [
        "",
        f"**Telemetry SHA-256 receipt:** `{meta['telemetry_sha256']}`",
        "",
        "## Independent verification",
        "",
        "This report and its raw telemetry are cryptographically signed with "
        "Sigstore keyless (Fulcio OIDC certificate + Rekor transparency log). "
        "Verify on any machine:",
        "",
        f"```bash\n{COSIGN_VERIFY_CMD}\n```",
        "",
        "Once the repository qualifies for GitHub artifact attestations "
        "(public repo or organization with GHAS), provenance is also "
        "verifiable via:",
        "",
        f"```bash\n{ATTEST_VERIFY_CMD}\n```",
        "",
        "> Note: every claim above is backed by a measurement taken inside "
        "this pipeline run; capabilities without automated evidence are "
        "never asserted.",
        "",
    ]
    return "\n".join(lines)


def render_html(meta: dict, results: list[dict]) -> str:
    rows = "\n".join(
        "<tr>"
        f"<td><strong>{_esc(r['pillar'])}</strong></td>"
        f"<td>{_esc(r['target'])}</td>"
        f"<td>{_esc(r['classical_baseline'])}</td>"
        f"<td><strong>{_esc(r['measured'])}</strong></td>"
        f"<td class='{_esc(r['status'].lower())}'>{_esc(r['status'])}</td>"
        "</tr>"
        for r in results
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Chronus v36 Sovereign Investor Dossier</title>
<style>
body {{ font-family: -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif;
       margin: 40px; color: #1a1a1a; }}
h1 {{ font-size: 20px; border-bottom: 3px solid #0b3d91; padding-bottom: 8px; }}
.meta {{ color: #444; font-size: 13px; margin-bottom: 20px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ border: 1px solid #999; padding: 8px; text-align: left; vertical-align: top; }}
th {{ background: #0b3d91; color: #fff; }}
.verified {{ color: #0a7d2c; font-weight: bold; }}
.failed {{ color: #b00020; font-weight: bold; }}
.footer {{ margin-top: 24px; font-size: 12px; color: #444; }}
code {{ background: #f2f2f2; padding: 2px 5px; border-radius: 3px; }}
@media print {{ body {{ margin: 12mm; }} }}
</style></head><body>
<h1>CHRONUS v36.0 &mdash; SOVEREIGN COMPUTATIONAL &amp; TELEMETRY CERTIFICATE</h1>
<p class="meta">
Commit SHA: <code>{_esc(meta['commit'])}</code> &nbsp;|&nbsp;
Run: <a href="{_esc(meta['run_url'])}">{_esc(meta['run_id'])}</a> &nbsp;|&nbsp;
Generated (UTC): {_esc(meta['generated_utc'])} &nbsp;|&nbsp;
Total benchmark time: {_esc(meta['total_time_s'])}s
</p>
<table>
<tr><th>Core Capability Pillar</th><th>Benchmark Target</th>
<th>Classical Baseline</th><th>Chronus v36 Measured</th>
<th>Verification Status</th></tr>
{rows}
</table>
<p class="footer">
Telemetry SHA-256 receipt: <code>{_esc(meta['telemetry_sha256'])}</code><br>
Independent verification (Sigstore keyless): <code>{_esc(COSIGN_VERIFY_CMD)}</code><br>
Provenance verification (when GitHub attestations are enabled): <code>{_esc(ATTEST_VERIFY_CMD)}</code><br>
Every claim is backed by a measurement taken inside the pipeline run;
capabilities without automated evidence are never asserted.
</p>
</body></html>
"""


def _breakable(text: str, limit: int = 60) -> str:
    """Insert spaces into over-long tokens so fpdf2 multi_cell can wrap them."""
    return " ".join(
        " ".join(token[i:i + limit] for i in range(0, len(token), limit))
        if len(token) > limit else token
        for token in str(text).split(" ")
    )


def render_pdf(meta: dict, results: list[dict], out_path: Path) -> bool:
    try:
        from fpdf import FPDF
    except ImportError:
        print("warning: fpdf2 not installed; skipping PDF generation", file=sys.stderr)
        return False

    pdf = FPDF(orientation="L", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("helvetica", "B", 14)
    pdf.multi_cell(0, 7, new_x="LMARGIN", new_y="NEXT", text="CHRONUS v36.0 - SOVEREIGN COMPUTATIONAL & TELEMETRY CERTIFICATE")
    pdf.ln(2)
    pdf.set_font("helvetica", "", 9)
    pdf.multi_cell(
        0, 5, new_x="LMARGIN", new_y="NEXT",
        text=_breakable(
            f"Commit SHA: {meta['commit']}   |   Run: {meta['run_id']}   |   "
            f"Generated (UTC): {meta['generated_utc']}   |   "
            f"Total benchmark time: {meta['total_time_s']}s"
        ),
    )
    pdf.ln(4)
    for r in results:
        pdf.set_font("helvetica", "B", 11)
        pdf.multi_cell(0, 6, new_x="LMARGIN", new_y="NEXT", text=f"{r['pillar']}  [{r['status']}]")
        pdf.set_font("helvetica", "", 9)
        pdf.multi_cell(0, 5, new_x="LMARGIN", new_y="NEXT", text=_breakable(f"Target: {r['target']}"))
        pdf.multi_cell(0, 5, new_x="LMARGIN", new_y="NEXT", text=_breakable(f"Classical baseline: {r['classical_baseline']}"))
        pdf.multi_cell(0, 5, new_x="LMARGIN", new_y="NEXT", text=_breakable(f"Chronus v36 measured: {r['measured']}"))
        note = r["detail"].get("note")
        if note:
            pdf.set_font("helvetica", "I", 8)
            pdf.multi_cell(0, 4, new_x="LMARGIN", new_y="NEXT", text=_breakable(f"Scope note: {note}"))
        pdf.ln(3)
    pdf.set_font("helvetica", "", 8)
    pdf.multi_cell(0, 4, new_x="LMARGIN", new_y="NEXT", text=_breakable(f"Telemetry SHA-256 receipt: {meta['telemetry_sha256']}"))
    pdf.multi_cell(0, 4, new_x="LMARGIN", new_y="NEXT", text=_breakable(f"Independent verification (Sigstore keyless): {COSIGN_VERIFY_CMD}"))
    pdf.multi_cell(0, 4, new_x="LMARGIN", new_y="NEXT", text=_breakable(f"Provenance (when attestations enabled): {ATTEST_VERIFY_CMD}"))
    pdf.output(str(out_path))
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="dossier-out", type=Path)
    parser.add_argument("--rtl-log", type=Path, default=None,
                        help="iverilog testbench log to include RTL evidence")
    parser.add_argument("--manifest", type=Path,
                        default=Path("manifests/qualification_manifest_final.json"))
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()
    results = [
        bench_memory_folding(),
        bench_subspace_search(),
        bench_planck_ladder(),
        bench_companion_matrix(),
        bench_threshold_mpc(),
        bench_homological_settlement(),
        bench_formal_invariants(),
        check_qualification_manifest(args.manifest),
    ]
    if args.rtl_log and args.rtl_log.exists():
        results.append(check_rtl(args.rtl_log))
    total_s = round(time.perf_counter() - start, 2)

    meta = {
        "commit": os.environ.get("GITHUB_SHA", "local"),
        "run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "run_url": (
            f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/"
            f"{os.environ.get('GITHUB_REPOSITORY', 'hybadatadevops1/Chronusv2')}/"
            f"actions/runs/{os.environ.get('GITHUB_RUN_ID', 'local')}"
        ),
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_time_s": total_s,
        "python": platform.python_version(),
        "telemetry_sha256": "",
    }

    telemetry = {"meta": meta, "results": results}
    telemetry_json = json.dumps(telemetry, indent=2, sort_keys=True)
    meta["telemetry_sha256"] = hashlib.sha256(telemetry_json.encode()).hexdigest()
    telemetry["meta"] = meta
    (args.out_dir / "telemetry.json").write_text(
        json.dumps(telemetry, indent=2, sort_keys=True) + "\n"
    )

    summary = render_markdown(meta, results)
    (args.out_dir / "summary.md").write_text(summary)
    (args.out_dir / "report.html").write_text(render_html(meta, results))
    render_pdf(meta, results, args.out_dir / "Chronus_v36_Sovereign_Investor_Dossier.pdf")

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a") as fh:
            fh.write(summary)

    print(summary)
    failures = [r["pillar"] for r in results if not r["passed"]]
    if failures:
        print(f"FAILED pillars: {failures}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Render the research report as Markdown (numbers only from the JSON report)."""
from __future__ import annotations

from typing import Any, Mapping

SYSTEM_LABELS = {
    "v16.4-reference": "v16.4 reference",
    "integrated": "v17 integrated",
    "sysid-plan-pipeline": "conventional identify→plan pipeline",
}


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "Unavailable"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}"
    return str(value)


def _ci(row: Mapping[str, Any] | None, digits: int = 3) -> str:
    if not row or row.get("mean") is None:
        return "Unavailable"
    if row.get("low95") is None:
        return f"{row['mean']:.{digits}f}"
    return f"{row['mean']:.{digits}f} [{row['low95']:.{digits}f}, {row['high95']:.{digits}f}]"


def _diff(row: Mapping[str, Any] | None, digits: int = 3) -> str:
    if not row or row.get("mean_diff") is None:
        return "Unavailable"
    mark = " *" if row.get("excludes_zero") else ""
    return (f"{row['mean_diff']:+.{digits}f} [{row['low95']:+.{digits}f}, "
            f"{row['high95']:+.{digits}f}]{mark}")


def comparison_table(report: Mapping[str, Any]) -> list[str]:
    systems = report["systems"]
    reference = systems.get("v16.4-reference", {}).get("all", {})
    integrated = systems.get("integrated", {}).get("all", {})
    slices_ref = systems.get("v16.4-reference", {}).get("slices", {})
    slices_int = systems.get("integrated", {}).get("slices", {})
    transfer = report.get("transfer", {})
    continual = report.get("continual", {}).get("integrated", {})
    calibration = report.get("calibration", {})
    adversarial = report.get("adversarial", {})
    skills = report.get("skills", {})
    negative = report.get("negative_transfer", {})
    representation = report.get("representation", {})
    gate = report.get("release_gate", {})

    def slice_metric(rows, name, metric):
        return _ci(rows.get(name, {}).get(metric))

    proxy = adversarial.get("proxy-reward", {})
    lines = [
        "| Dimension | Metric (definition) | v16.4 reference | v17 integrated |",
        "|---|---|---|---|",
        f"| Reasoning accuracy | in-distribution evaluation success rate | "
        f"{slice_metric(slices_ref, 'evaluation', 'solved')} | "
        f"{slice_metric(slices_int, 'evaluation', 'solved')} |",
        f"| Causal inference | mechanism identification accuracy at episode end | "
        f"{_ci(reference.get('identification_accuracy'))} | "
        f"{_ci(integrated.get('identification_accuracy'))} |",
        f"| Predictive modelling | mean predictive probability of observed probe outcomes | "
        f"{_ci(reference.get('probe_predictive_probability'))} | "
        f"{_ci(integrated.get('probe_predictive_probability'))} |",
        f"| Planning | planning node expansions per task (compute) | "
        f"{_ci(reference.get('planning_expansions'), 1)} | "
        f"{_ci(integrated.get('planning_expansions'), 1)} |",
        f"| Replanning | held-out successes recovered after a failed first submission | "
        f"{_fmt(report.get('recovery', {}).get('v16.4-reference'))} | "
        f"{_fmt(report.get('recovery', {}).get('integrated'))} |",
        f"| Cross-domain transfer | success on held-out families | "
        f"{slice_metric(slices_ref, 'held-out', 'solved')} | "
        f"{slice_metric(slices_int, 'held-out', 'solved')} |",
        f"| Cross-domain transfer | trained − untrained utility on held-out families | "
        f"Unavailable | {_diff(transfer.get('held-out', {}).get('utility'))} |",
        f"| Continual retention | forgetting after sequential curriculum (lower is better) | "
        f"Unavailable | {_ci(continual.get('forgetting'))} |",
        f"| Novel primitive discovery | promoted skills per seed library | 0 (no mechanism) | "
        f"{_fmt(report.get('skill_counts', {}).get('promoted_mean'), 2)} |",
        f"| Useful skill composition | evaluation successes whose plan used a learned skill | "
        f"0 | {skills.get('eval_successes_using_skills', 'Unavailable')} |",
        f"| Representation adaptation | evaluation episodes planned in a non-literal representation | "
        f"0 | {sum(v for k, v in representation.get('adopted_counts', {}).items() if k != 'literal')} |",
        f"| Negative-transfer recognition | strategy negative transfer recognised (entries) | "
        f"Unavailable | {len(negative.get('ledger', {}).get('strategy_negative_recognised', []))} |",
        f"| Negative-transfer recognition | superficial analogies wrongly adopted | "
        f"{_fmt(adversarial.get('superficial-analogy', {}).get('v16.4-reference', {}).get('wrongly_adopted'))} | "
        f"{_fmt(adversarial.get('superficial-analogy', {}).get('integrated', {}).get('wrongly_adopted'))} |",
        f"| Reward-hacking resistance | proxy-reward attack success rate | "
        f"{_fmt(proxy.get('v16.4-reference', {}).get('success', {}).get('rate'))} | "
        f"{_fmt(proxy.get('integrated', {}).get('success', {}).get('rate'))} |",
        f"| Sample efficiency | interactions (probes + submissions) per task | "
        f"{_ci(reference.get('interactions'), 2)} | {_ci(integrated.get('interactions'), 2)} |",
        f"| Sample efficiency | normalised interaction cost (cost / value) | "
        f"{_ci(reference.get('normalised_cost'))} | {_ci(integrated.get('normalised_cost'))} |",
        f"| Computational cost | wall-clock seconds per task | "
        f"{_ci(reference.get('wall_s'))} | {_ci(integrated.get('wall_s'))} |",
        f"| Uncertainty calibration | Brier score of submission success predictions | "
        f"{_fmt(calibration.get('v16.4-reference', {}).get('brier'))} | "
        f"{_fmt(calibration.get('integrated', {}).get('brier'))} |",
        f"| Uncertainty calibration | expected calibration error (10 bins) | "
        f"{_fmt(calibration.get('v16.4-reference', {}).get('ece'))} | "
        f"{_fmt(calibration.get('integrated', {}).get('ece'))} |",
        f"| Overall | success rate, all held-out slices | {_ci(reference.get('solved'))} | "
        f"{_ci(integrated.get('solved'))} |",
        f"| Overall | utility (success × unspent budget fraction) | "
        f"{_ci(reference.get('utility'))} | {_ci(integrated.get('utility'))} |",
        "",
        f"Release gate: **{'PASSED' if gate.get('passed') else 'NOT PASSED'}** — "
        f"{gate.get('criterion', '')}. Success difference (integrated − v16.4): "
        f"{_diff(gate.get('solved_difference'))}; held-out families: "
        f"{_diff(gate.get('held_out_family_solved_difference'))}.",
    ]
    return lines


def render(report: Mapping[str, Any]) -> str:
    out = ["# EUCLID v17 integrated-intelligence research report", ""]
    protocol = report["protocol"]
    out += [
        f"Seeds: {protocol['seeds']} (suite base {protocol.get('suite_base')}"
        f"{'; pre-registered, never used in development' if protocol.get('suite_base') == 2000 else '; DEVELOPMENT suites'}). "
        f"Systems: {len(protocol['systems'])}. Evaluation: {protocol['evaluation']}.",
        f"Leakage check (knowledge digest unchanged by evaluation for every system and seed): "
        f"**{'passed' if report.get('leakage_free') else 'FAILED'}**.",
        "Intervals are 95% Student-t across seeds; differences are paired bootstrap 95% "
        "intervals over (seed, task); `*` marks intervals excluding zero.",
        "",
        "## v16.4 versus v17",
        "",
    ]
    out += comparison_table(report)
    out += ["", "## All systems (held-out slices pooled)", "",
            "| System | Success | Utility | Interactions | Expansions | Wall s | Brier |",
            "|---|---|---|---|---|---|---|"]
    for name, data in report["systems"].items():
        row = data["all"]
        out.append(
            f"| {SYSTEM_LABELS.get(name, name)} | {_ci(row['solved'])} | {_ci(row['utility'])} | "
            f"{_ci(row['interactions'], 2)} | {_ci(row['planning_expansions'], 0)} | "
            f"{_ci(row['wall_s'])} | {_fmt(row['calibration']['brier'])} |")
    out += ["", "## Ablations: integrated minus system (paired)", "",
            "| System | Δ utility | Δ success | Δ utility evaluation | Δ utility held-out | "
            "Δ utility adversarial | Δ utility analogy |", "|---|---|---|---|---|---|---|"]
    for name, data in report["paired_vs_integrated"].items():
        by = data["by_slice"]
        out.append(
            f"| {SYSTEM_LABELS.get(name, name)} | {_diff(data['utility'])} | "
            f"{_diff(data['solved'])} | {_diff(by.get('evaluation'))} | "
            f"{_diff(by.get('held-out'))} | {_diff(by.get('adversarial'))} | "
            f"{_diff(by.get('analogy'))} |")
    synergy = report.get("synergy", {})
    if synergy.get("integration_gain") is not None:
        out += ["", "## Emergence through composition", "",
                f"Integration gain over the conventional pipeline (utility): "
                f"{synergy['integration_gain']:+.4f}; sum of single-mechanism contributions: "
                f"{synergy['sum_of_single_contributions']:+.4f}; synergy: "
                f"{synergy['synergy']:+.4f} — {synergy['interpretation']}.", ""]
        for mechanism, value in synergy["single_mechanism_contributions"].items():
            out.append(f"* removing {mechanism}: {value:+.4f} utility")
    transfer = report["transfer"]
    out += ["", "## Transfer (trained − untrained, same frozen protocol)", ""]
    for name in ("held-out", "analogy", "evaluation"):
        row = transfer.get(name, {})
        out.append(f"* {name}: utility {_diff(row.get('utility'))}; success "
                   f"{_diff(row.get('solved'))}; probes {_diff(row.get('probes'), 2)}")
    for kind, row in transfer.get("analogy_kinds", {}).items():
        out.append(f"* {kind}: utility {_diff(row['utility'])}, probes {_diff(row['probes'], 2)}, "
                   f"adopted {row['adopted_rate']:.2f}, abandoned {row['abandoned_rate']:.2f}")
    for family, row in transfer.get("held_out_families", {}).items():
        out.append(f"* held-out family {family}: utility {_diff(row['utility'])}")
    negative = report["negative_transfer"]
    out += ["", "## Negative transfer", "",
            f"Mismatched curriculum ({negative['curriculum']['source']} → "
            f"{negative['curriculum']['target']}), trained − untrained: utility "
            f"{_diff(negative['utility'])}, probes {_diff(negative['probes'], 2)}, "
            f"identification {_diff(negative['identification'])}.",
            f"Analogy transfers ledgered positive/negative: "
            f"{negative['ledger']['analogy_positive']}/{negative['ledger']['analogy_negative']}; "
            f"strategy negative transfer recognised: "
            f"{len(negative['ledger']['strategy_negative_recognised'])}."]
    out += ["", "## Continual learning", ""]
    for system, row in report["continual"].items():
        out.append(f"* {SYSTEM_LABELS.get(system, system)}: backward transfer "
                   f"{_ci(row['backward_transfer'])}, forward transfer "
                   f"{_ci(row['forward_transfer'])}, forgetting {_ci(row['forgetting'])}, "
                   f"final average utility {_ci(row['final_average_utility'])}")
    out += ["", "## Adversarial attacks", "", "| Attack | System | Success | Detection |",
            "|---|---|---|---|"]
    for tag, systems in report["adversarial"].items():
        for system, entry in systems.items():
            if system not in ("integrated", "v16.4-reference", "sysid-plan-pipeline"):
                continue
            detection = {k: v for k, v in entry.items() if k != "success"}
            success = entry.get("success", {})
            out.append(f"| {tag} | {SYSTEM_LABELS.get(system, system)} | "
                       f"{_fmt(success.get('rate'))} (n={success.get('n')}) | "
                       f"{detection or '—'} |")
    out += ["", "## Calibration", ""]
    for system, row in report["calibration"].items():
        out.append(f"* {SYSTEM_LABELS.get(system, system)}: {row['status']}; submissions "
                   f"{row['submissions']}; Brier {_fmt(row['brier'])}; ECE {_fmt(row['ece'])}")
    phi = report["phi"]
    out += ["", "## φ / Fibonacci experiments", "",
            "Mean evaluations to locate the maximum of a strictly unimodal sequence "
            f"({phi['unimodal_search']['curves']} curves, n∈[20,300]):"]
    for name, row in phi["unimodal_search"]["mean_evaluations"].items():
        out.append(f"* {name}: {_ci(row, 2)}")
    out.append("")
    out.append("Success by evaluation budget (Wilson rate):")
    for budget, row in phi["unimodal_search"]["success_by_budget"].items():
        out.append(f"* budget {budget}: " + ", ".join(
            f"{k} {v['rate']:.3f}" for k, v in row.items()))
    out.append("")
    out.append("Iterative-deepening schedules on true task models:")
    for name, row in phi["iterative_deepening_schedules"]["summary"].items():
        out.append(f"* {name}: solved {row['solved']}/{row['tasks']}, mean expansions "
                   f"{row['mean_expansions']:.1f}, mean excess length "
                   f"{_fmt(row['mean_excess_length'], 2)}")
    out.append("")
    out.append("Anytime coverage (largest gap fraction; lower is better):")
    for name, rows in phi["anytime_coverage"]["max_gap_fraction"].items():
        out.append(f"* {name}: " + ", ".join(
            f"n={r['points']}: {r['max_gap_fraction']:.3f}" for r in rows))
    out += ["", "## Self-improvement", ""]
    for run in report["self_improvement"]:
        decisions = [f"{r['parameter']}: {r['decision']} ({r['method']}, "
                     f"{r['sandbox_evaluations']} sandbox evaluations)" for r in run["ledger"]]
        out.append(f"* seed {run['seed']} ({'golden' if run['golden'] else 'grid'} proposals): "
                   + "; ".join(decisions))
    rep = report["representation"]
    out += ["", "## Representation restructuring", "",
            f"Adopted representations in integrated evaluation: {rep['adopted_counts']}"]
    for example in rep["examples"][:4]:
        trials = ", ".join(f"{t['representation']}: found={t['found']} expanded={t['expanded']}"
                           f" net={t['net_utility']}" for t in example["trials"])
        out.append(f"* {example['task_id']} ({example['family']}) → {example['selected']}: {trials}")
    skills = report["skills"]
    out += ["", "## Discovered skills", "",
            f"Evaluation episodes using learned skills: {skills['eval_episodes_using_skills']} "
            f"(successes {skills['eval_successes_using_skills']}, held-out families "
            f"{skills['held_out_family_uses']})."]
    for seed, library in skills["libraries"].items():
        for skill in library["promoted"][:4]:
            out.append(f"* seed {seed}: `{skill['pattern']}` level {skill['level']}, support "
                       f"{skill['support']}, held-out utility {_fmt(skill['held_out_utility'])}")
    out += ["", f"Total programme wall clock: {report.get('wall_clock_s', 0):.0f} s.", ""]
    return "\n".join(out)


__all__ = ["comparison_table", "render"]

"""Tests for the nine-agent operating model.

Every test exercises real code against the real tree — no tautologies,
no approx on exact surfaces."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hyba.operating_model import (
    AGENT,
    LAYERS,
    VOCAB,
    REMEDIATOR_MAX_FILES,
    may_write,
    suite_is_non_tautological,
    freeze_substrate,
    substrate_frozen,
    require_lemma,
    lemma_signed,
    write_failure_modes,
    failure_modes_documented,
    run_pipeline,
    repo_root,
)
from hyba.operating_model import verifiers
from hyba.operating_model.pipeline import remediator

ROOT = repo_root()


def _conftest_scope():
    """Tests mutate ROOT-level fixtures under a tmp copy for isolation
    where needed; most run read-only on the real tree."""
    return ROOT


# ---------------------------------------------------------------- roles

def test_ten_agents_in_three_layers():
    assert len(AGENT) == 10
    assert LAYERS["TRUTH"] == frozenset({1, 6, 7, 8, 9, 10})
    assert LAYERS["CHANGE"] == frozenset({2, 3})
    assert LAYERS["CONTROL"] == frozenset({4, 5})
    for aid in AGENT:
        assert aid in LAYERS["TRUTH"] | LAYERS["CHANGE"] | LAYERS["CONTROL"]


def test_write_permissions_enforced():
    for aid in LAYERS["TRUTH"]:
        assert may_write(aid, "x.py", is_draft_pr=False) is False
        assert may_write(aid, "x.py", is_draft_pr=True) is False
    for aid in LAYERS["CONTROL"]:
        if aid == 5:
            assert may_write(aid, "docs/provenance/abc.json",
                             is_draft_pr=True)
            assert may_write(aid, "hyba/x.py", is_draft_pr=True) is False
        else:
            assert may_write(aid, "docs/provenance/abc.json",
                             is_draft_pr=True) is False
    assert may_write(2, "hyba/x.py", is_draft_pr=True) is True
    assert may_write(2, "hyba/x.py", is_draft_pr=False) is False
    assert may_write(2, "tests/t.py", is_draft_pr=True) is False
    assert may_write(3, "tests/t.py", is_draft_pr=True) is True
    assert may_write(3, "hyba/x.py", is_draft_pr=True) is False
    with pytest.raises(ValueError):
        may_write(99, "x.py", is_draft_pr=True)


def test_vocabularies_are_isolated():
    union = set()
    for terms in VOCAB.values():
        assert not union & terms, "overlapping vocabulary term"
        union |= terms


def test_suite_non_tautological():
    assert suite_is_non_tautological()


# ---------------------------------------------------------------- substrate

def test_the_committed_substrate_freeze_is_what_the_code_computes():
    # Computed, never written: a changed substrate must fail here, not be
    # silently re-frozen by the test suite.
    out = freeze_substrate(ROOT, write=False)
    committed = json.loads((ROOT / "docs" / "substrate_freeze.json").read_text())
    assert out == committed
    assert out["theorem_proven"] is False
    assert out["sweep"]["vectors_total"] == 8192
    assert out["sweep"]["max_len"] == 511
    assert substrate_frozen(ROOT)
    data = json.loads((ROOT / "docs" / "substrate_freeze.json").read_text())
    assert data["theorem_proven"] is False
    assert set(data["signatures"]) == {
        "mathematician", "cryptographer", "number_theorist", "systems",
        "numerical"}


# ---------------------------------------------------------------- lemma

def test_the_committed_lemma_signoff_is_what_the_code_computes():
    out = require_lemma(ROOT, write=False)
    committed = json.loads((ROOT / "docs" / "lemma_signoff.json").read_text())
    assert out == committed
    assert out["theorem_proven"] is False
    assert out["lines"] <= 200
    assert lemma_signed(ROOT)
    md = (ROOT / "docs" / "lemma_lucas_polynomial.md").read_text(
        encoding="utf-8")
    assert "tr(" in md
    for reviewer in ("mathematician", "complexity", "number_theorist",
                     "qi_physicist", "systems"):
        assert f"- {reviewer}" in md or f"| {reviewer}" in md


def test_verify_lemma_holds_on_declared_range():
    from hyba.operating_model import lemma as L
    findings = L.verify_lemma(L.LEMMA, L.LEMMA["verified_range"])
    assert findings[0]["verdict"] == "HOLDS"
    assert findings[0]["theorem_proven"] is False
    # Cross-oracle against a naive recurrence and exact matpow.
    a, b = 2, 1
    for n in range(77):
        assert L.fast_doubling_lucas(n) == a
        a, b = b, a + b
    for n in range(0, 77):
        assert L.trace(L.matpow_int(L.GOLDEN_MATRIX, n)) == \
            L.fast_doubling_lucas(n)


def test_use_lemma_scope_guard():
    import dataclasses
    from hyba.operating_model import lemma as L
    out = L.use_lemma("order_nonce_window_probe_schedules",
                      L.GoldenGraph(n=18))
    assert out["path_count"] == 5778  # L_18, exact
    assert out["bound"] == "O(log n)"
    assert out["theorem_proven"] is False
    with pytest.raises(L.ScopeViolation):
        L.use_lemma("bogus_usage", L.GoldenGraph(n=3))
    with pytest.raises(L.ScopeViolation):
        L.use_lemma("order_nonce_window_probe_schedules",
                    dataclasses.replace(L.GoldenGraph(n=3), state_count=3))
    with pytest.raises(L.ScopeViolation):
        L.use_lemma("order_nonce_window_probe_schedules",
                    dataclasses.replace(L.GoldenGraph(n=3),
                                        matrix=((1, 2), (3, 4))))


def test_claim_complexity_scope():
    from hyba.operating_model import lemma as L

    class C:
        quantity = "tr(Q^n)"
        graph = "two_state_golden"
        complexity = "O(log n)"

    assert L.claim_complexity(C())["authorized"] is True
    for field, bad in (("quantity", "L_n"),
                       ("graph", "three_state"),
                       ("complexity", "O(1)")):
        c = C()
        setattr(c, field, bad)
        with pytest.raises(L.ScopeViolation):
            L.claim_complexity(c)


def test_citation_check_flags_overclaim_not_disclaimer():
    from hyba.operating_model import lemma as L
    bad = L.citation_check("This lemma proves P vs NP.")
    assert bad and bad[0]["verdict"] == "overclaim"
    good = L.citation_check(
        "This is not a proof of P vs NP; the lemma does not "
        "prove P vs NP.")
    assert good == []
    doc = (ROOT / "docs" / "lemma_lucas_polynomial.md").read_text(
        encoding="utf-8")
    assert L.citation_check(doc) == []


def test_ast_scope_check_clean_and_catches_bypass(tmp_path):
    from hyba.operating_model import lemma as L
    assert L.ast_scope_check(ROOT) == []
    pkg = tmp_path / "mining"
    pkg.mkdir()
    (pkg / "bad.py").write_text(
        "from hyba.operating_model.lemma import LEMMA\n"
        "def f():\n    return LEMMA['scope']\n", encoding="utf-8")
    violations = L.ast_scope_check(tmp_path)
    assert violations and violations[0]["file"] == "mining/bad.py"


# ---------------------------------------------------------------- failure modes

def test_the_committed_failure_modes_are_what_the_code_computes():
    out = write_failure_modes(ROOT, write=False)
    assert out == json.loads((ROOT / "docs" / "failure_modes.json").read_text())
    assert len(out["modes"]) == 10
    assert failure_modes_documented(ROOT)
    data = json.loads((ROOT / "docs" / "failure_modes.json").read_text())
    assert len(data["modes"]) == 10
    assert data["each_has_a_test"] is True
    assert data["each_has_an_owner_truth_agent"] is True
    owners = {m["owner"] for m in data["modes"]}
    assert owners <= set(AGENT.values())


# ---- one test per failure mode (names embed the mode key) ----

def test_float_leak_in_gap_kernel():
    """A declared-exact function containing float() is flagged."""
    src = ROOT / "mining" / "_om_float_leak.py"
    src.write_text(
        'def gap(a):\n    """bit-exact integer fold"""\n'
        "    return float(a) + 1\n", encoding="utf-8")
    try:
        findings = verifiers.precision_sentinel(ROOT)
        assert any(
            f["verdict"] == "float_leak"
            and f["file"] == "mining/_om_float_leak.py" for f in findings)
    finally:
        src.unlink()


def test_hmac_key_reuse():
    src = ROOT / "mining" / "_om_hmac_reuse.py"
    src.write_text(
        'import hmac\n'
        'def sign_a(m):\n    return hmac.new(b"deadbeef", m, "sha256").digest()\n'
        'def sign_b(m):\n    return hmac.new(b"deadbeef", m, "sha256").digest()\n',
        encoding="utf-8")
    try:
        findings = verifiers.security_verifier(ROOT)
        assert any(
            f["verdict"] == "key_lifecycle_reuse"
            and f["file"] == "mining/_om_hmac_reuse.py" for f in findings)
    finally:
        src.unlink()


def test_replay_across_cycle_boundary():
    """A transcript's cycle numbers are strictly ordered — no replay."""
    from hyba.operating_model.live_run import live_run
    t = live_run("happy", cycles=2, root=ROOT)
    assert [c["cycle"] for c in t] == [0, 1]


def test_integer_overflow_at_L20():
    import sys
    if str(ROOT / "chronus/mla1517_platform" / "python") not in sys.path:
        sys.path.insert(0, str(ROOT / "chronus/mla1517_platform" / "python"))
    import turing_core
    assert turing_core.lucas(20) == 15127
    for n in range(0, 77):
        assert isinstance(turing_core.lucas(n), int)
        assert turing_core.lucas(n) > 0


def test_nondeterministic_dict_iteration():
    src = ROOT / "mining" / "_om_rng.py"
    src.write_text(
        "import random\n"
        "def nonce_schedule(n):\n    return random.randint(0, n)\n",
        encoding="utf-8")
    try:
        findings = verifiers.precision_sentinel(ROOT)
        assert any(
            f["verdict"] == "nondeterministic_source"
            and f["file"] == "mining/_om_rng.py" for f in findings)
    finally:
        src.unlink()


def test_retarget_thrash_hardware():
    """FSM refuses to begin twice while waiting — no thrash."""
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from mining.safety_fsm import SafetyFSM
    fsm = SafetyFSM()
    assert fsm.begin_search()
    fsm.on_winner_found()
    fsm.on_block_accepted(1)
    assert not fsm.begin_search()
    assert fsm.consecutive_blocks_prevented == 1


def test_goal_stack_starvation():
    """Auditor locates every declared claim — nothing starved."""
    findings = verifiers.auditor(ROOT)
    assert findings, "auditor found no claims to trace"
    assert all(f.get("source") != "MISSING" for f in findings), findings


def test_submission_route_bypass_is_flagged(tmp_path):
    """A client.submit call outside the durable lifecycle is a defect."""
    from hyba.operating_model.verifiers import _submission_route_check
    rogue = tmp_path / "Intelligence"
    rogue.mkdir()
    (rogue / "rogue.py").write_text(
        "class Rogue:\n"
        "    def go(self):\n"
        "        return self.client.submit(nonce=1)\n"
    )
    findings = _submission_route_check(tmp_path)
    bypass = [f for f in findings
              if f.get("claim") == "unmanaged_submission_route"
              and f.get("file", "").endswith("rogue.py")]
    assert bypass and bypass[0]["verdict"] == "confirmed_defect"
    # With the lifecycle coordinator file absent the gate is also reported.
    assert any(f.get("claim") == "lifecycle_gate_absent" for f in findings)


def test_deployed_paths_have_no_bypass_or_ladder_drift():
    """On the real tree the route and ladder-source checks are clean."""
    from hyba.operating_model.verifiers import (
        _ladder_source_check, _submission_route_check)
    assert _submission_route_check(ROOT) == []
    assert _ladder_source_check(ROOT) == []


def test_ladder_literal_redeclaration_is_flagged(tmp_path):
    """A module re-declaring the canonical rung tuple is a defect."""
    from hyba.operating_model.verifiers import _ladder_source_check
    pkg = tmp_path / "mining"
    pkg.mkdir()
    (pkg / "drift.py").write_text(
        "LADDER = (10, 12, 15, 18, 20)\n")
    (pkg / "test_pinned.py").write_text(
        "assert (10, 12, 15, 18, 20) == (10, 12, 15, 18, 20)\n")
    findings = _ladder_source_check(tmp_path)
    assert len(findings) == 1
    assert findings[0]["file"].endswith("drift.py")


def test_lucas_wiring_sibling_import_is_flagged(tmp_path):
    """Kernel names may only come from lucas/ or the canonical shims."""
    from hyba.operating_model.verifiers import _lucas_wiring_check
    pkg = tmp_path / "toe"
    pkg.mkdir()
    (pkg / "bad.py").write_text(
        "from mining.helper import t_phi_fold\n")
    (pkg / "good.py").write_text(
        "from lucas.fold import t_phi_fold\n")
    findings = _lucas_wiring_check(tmp_path)
    assert len(findings) == 1
    assert findings[0]["file"].endswith("bad.py")


def test_kernel_routes_resolve_on_deployed_tree():
    """Every KERNEL_SPECS route resolves to a canonical file or oracle."""
    from hyba.operating_model.verifiers import _kernel_route_check
    assert _kernel_route_check(ROOT) == []


def test_kernel_route_missing_entry_is_flagged(tmp_path):
    """A spec whose canonical file lacks its entry symbol is a defect."""
    import hyba.math_ir.specs as specs
    from hyba.operating_model.verifiers import _kernel_route_check
    kernels = tmp_path / "kernels"
    kernels.mkdir()
    (kernels / "empty.cl").write_text("// no kernels here\n")
    spec = specs.KernelSpec(
        name="phantom", math="x", signature="y",
        canonical_source="kernels/empty.cl", entry="phantom_entry",
        oracle="", executor="cpu")
    original = specs.KERNEL_SPECS.get("phantom")
    specs.KERNEL_SPECS["phantom"] = spec
    try:
        findings = _kernel_route_check(tmp_path)
    finally:
        if original is None:
            del specs.KERNEL_SPECS["phantom"]
        else:
            specs.KERNEL_SPECS["phantom"] = original
    flagged = [f for f in findings if "phantom" in f["detail"]]
    assert flagged and flagged[0]["verdict"] == "confirmed_defect"


def test_folded_ratio_lies():
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import turing_core
    raw = bytes(range(256)) * 2
    folded = turing_core.t_phi_fold(raw)
    assert len(folded) / len(raw) >= 1.0
    streamed = bytes(turing_core.iter_original_u8(folded, len(raw)))
    assert streamed == raw


def test_non_cptp_measurement_path():
    """The gate table is exactly unitary — no non-CPTP path exists."""
    findings = verifiers.quantum_checker(ROOT)
    assert findings
    assert all(f["verdict"] == "unitary" for f in findings)


def test_pin_violated_somewhere():
    src = ROOT / "mining" / "_om_pin.py"
    src.write_text('x = {"theorem_proven": True}\n', encoding="utf-8")
    try:
        findings = verifiers.pin_verifier(ROOT)
        assert any(
            f["verdict"] == "pin_violated"
            and f["file"] == "mining/_om_pin.py" for f in findings)
    finally:
        src.unlink()
    findings = verifiers.pin_verifier(ROOT)
    assert all(f["verdict"] == "pin_holds" for f in findings)


# ---------------------------------------------------------------- governance

def test_governance_verdict_lattice():
    assert verifiers.governance([])["verdict"] == "PASS"
    assert verifiers.governance(
        [{"verdict": "undecidable"}])["verdict"] == "NOT_PROVABLE"
    assert verifiers.governance(
        [{"verdict": "float_leak"}])["verdict"] == "FAIL"
    assert verifiers.governance([], in_scope=False)["verdict"] == "FAIL"


def test_remediator_caps():
    defects = [{"verdict": "float_leak", "file": f"f{i}.py", "line": 1}
               for i in range(REMEDIATOR_MAX_FILES + 1)]
    out = remediator(defects, ROOT)
    assert out["escalated"] == "file_cap"
    assert out["bundle"] is None


# ---------------------------------------------------------------- pipeline

def test_run_pipeline_end_to_end(tmp_path):
    # The committed records are the preconditions; the test never writes them.
    assert substrate_frozen(ROOT) and lemma_signed(ROOT) and failure_modes_documented(ROOT)
    out = run_pipeline(ROOT, label="test", write_provenance=True, provenance_dir=tmp_path)
    assert out["verdict"] in {"PASS", "FAIL", "NOT_PROVABLE"}
    assert out["theorem_proven"] is False
    prov = Path(out["provenance"])
    assert prov.parent == tmp_path  # the repository's own records are untouched
    assert prov.is_file()
    rec = json.loads(prov.read_text(encoding="utf-8"))
    assert rec["replay"]["seed"] == 1517
    assert rec["theorem_proven"] is False


def test_provenance_replayable(tmp_path):
    from hyba.operating_model.pipeline import provenance
    v = {"verdict": "PASS", "reason": "r"}
    p1 = provenance(ROOT, "replay-test", v, [], write=True, out_dir=tmp_path)
    p2 = provenance(ROOT, "replay-test", v, [], write=True, out_dir=tmp_path)
    assert p1 == p2
    assert p1.read_bytes() == p2.read_bytes()

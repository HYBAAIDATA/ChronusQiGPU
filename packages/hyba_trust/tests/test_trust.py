import pytest

from hyba_trust import (
    Actor, AppealRefused, Atom, IllegalTransition, NotAuthorized, RiskTier, Role, SelfApproval,
    StaleReviewPacket, State, TrustError, TrustFabric, UseCase, check_invariants, consolidate, project,
)
from hyba_trust import metrics
from hyba_trust.model import DAY

ALICE = Actor.of("alice", Role.REVIEWER)
BOB = Actor.of("bob", Role.REVIEWER)
CARA = Actor.of("cara", Role.REVIEWER, Role.SIGNATORY)
DAN = Actor.of("dan", Role.SECOND_LINE)
ERIN = Actor.of("erin", Role.SECOND_LINE)
OWNER = Actor.of("olu", Role.DATA_OWNER)
BOT = Actor.of("auto", Role.AUTO_REVIEWER)


class Clock:
    def __init__(self):
        self.t = 1_000_000

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def fab(clock):
    return TrustFabric(clock=clock)


def atom(atom_id, tier=RiskTier.LOW, **kw):
    kw.setdefault("proposer", "pat")
    kw.setdefault("generating_agent", "agent-7")
    return Atom(id=atom_id, content=kw.pop("content", f"claim {atom_id}"), risk_tier=tier, **kw)


def approve(fab, atom_id, *reviewers):
    result = None
    for r in reviewers:
        result = fab.review(atom_id, r, "APPROVE", "checked evidence", fab.review_packet(atom_id))
    return result


def make_canonical(fab, clock, atom_id, **kw):
    fab.propose(atom(atom_id, **kw))
    approve(fab, atom_id, ALICE)
    clock.advance(30 * DAY)
    fab.tick()
    assert fab.atoms[atom_id].state is State.CANONICAL
    return fab.atoms[atom_id]


# ---------------------------------------------------------------- fix 1

def test_high_tier_needs_two_approvers_before_any_state_change(fab):
    fab.propose(atom("h", RiskTier.HIGH))
    assert approve(fab, "h", ALICE) == "awaiting_second_approver"
    assert fab.atoms["h"].state is State.PROPOSED          # v5 had already moved it to probation here
    assert approve(fab, "h", ALICE) == "awaiting_second_approver"  # the same person twice is still one
    assert approve(fab, "h", BOB) == "probation"
    assert fab.atoms["h"].state_history[-1].approvers == ("alice", "bob")
    assert check_invariants(fab) == []


def test_regulatory_needs_a_named_signatory(fab):
    fab.propose(atom("r", RiskTier.REGULATORY))
    approve(fab, "r", ALICE)
    assert approve(fab, "r", BOB) == "awaiting_signatory"
    assert approve(fab, "r", CARA) == "probation"


# ---------------------------------------------------------------- fix 2

def test_amender_becomes_author_and_cannot_approve(fab):
    fab.propose(atom("a"))
    p = fab.review_packet("a")
    fab.review("a", ALICE, "AMEND", "tightened wording", p, edits={"content": "better", "provenance": "alice v2"})
    with pytest.raises(SelfApproval):
        approve(fab, "a", ALICE)
    assert approve(fab, "a", BOB) == "probation"


def test_amendment_must_restamp_provenance_and_invalidates_old_packets(fab):
    fab.propose(atom("a"))
    old = fab.review_packet("a")
    with pytest.raises(TrustError):
        fab.review("a", ALICE, "AMEND", "x", old, edits={"content": "new"})
    fab.review("a", ALICE, "AMEND", "x", old, edits={"content": "new", "provenance": "alice"})
    with pytest.raises(StaleReviewPacket):
        fab.review("a", BOB, "APPROVE", "ok", old)


# ---------------------------------------------------------------- fix 3, 4

def test_cascade_disputes_probation_descendants_so_they_cannot_auto_promote(fab, clock):
    make_canonical(fab, clock, "root")
    fab.propose(atom("child", derived_from=("root",)))
    approve(fab, "child", BOB)
    assert fab.atoms["child"].state is State.PROBATION
    fab.transition("root", State.DEMOTED, ALICE, "source withdrawn")
    assert fab.atoms["child"].state is State.DISPUTED and fab.atoms["child"].stale
    clock.advance(31 * DAY)
    fab.tick()
    assert fab.atoms["child"].state is State.DISPUTED     # v5: auto-promoted to canonical
    assert check_invariants(fab) == []


def test_probation_atom_can_be_disputed(fab):
    fab.propose(atom("p"))
    approve(fab, "p", ALICE)
    fab.raise_dispute("p", BOB, "contradicts the filing")
    assert fab.atoms["p"].state is State.DISPUTED


# ---------------------------------------------------------------- fix 5

def test_cascade_visits_a_diamond_once_and_writes_one_manifest(fab, clock):
    make_canonical(fab, clock, "a")
    for x in ("b", "c"):
        make_canonical(fab, clock, x, derived_from=("a",))
    make_canonical(fab, clock, "d", kind="summary", derived_from=("b", "c"))
    manifest = fab.transition("a", State.DEMOTED, ALICE, "bad source")
    assert sorted(manifest.descendants) == ["b", "c", "d"]
    assert manifest.summaries == ("d",)
    assert len(fab.cascades) == 1
    assert sum(e.to_state is State.DISPUTED for e in fab.atoms["d"].state_history) == 1


def test_cascade_terminates_on_a_lineage_cycle(fab, clock):
    fab.propose(atom("x"))
    fab.propose(atom("y", derived_from=("x",)))
    fab.review("x", ALICE, "AMEND", "link", fab.review_packet("x"), edits={"derived_from": ["y"], "provenance": "a"})
    manifest = fab.transition("x", State.DEMOTED, BOB, "loop")
    assert manifest.descendants == ("y",)


# ---------------------------------------------------------------- fix 6

def test_unretract_needs_two_distinct_second_line_actors(fab):
    fab.propose(atom("t"))
    fab.transition("t", State.RETRACTED, OWNER, "published in error")
    with pytest.raises(NotAuthorized):
        fab.transition("t", State.QUARANTINED, DAN, "bring back")
    with pytest.raises(NotAuthorized):
        fab.unretract("t", [DAN], "bring back")
    with pytest.raises(NotAuthorized):
        fab.unretract("t", [DAN, ALICE], "bring back")
    task = fab.unretract("t", [DAN, ERIN], "new evidence")
    assert fab.atoms["t"].state is State.QUARANTINED and task.second_line_required


# ---------------------------------------------------------------- fix 7

def test_reviews_apply_to_freshly_proposed_atoms(fab):
    fab.propose(atom("ok"))
    fab.propose(atom("bad"))
    assert approve(fab, "ok", ALICE) == "probation"
    assert fab.review("bad", ALICE, "REJECT", "no evidence", fab.review_packet("bad")) == "demoted"


# ---------------------------------------------------------------- fix 8

def test_probation_is_not_decided_before_its_ttl(fab, clock):
    fab.propose(atom("p"))
    approve(fab, "p", ALICE)
    fab.record_serve("p", correct=False)
    clock.advance(10 * DAY)
    assert fab.tick()["probation_failed"] == []            # v5 demoted here, 20 days early
    assert fab.atoms["p"].state is State.PROBATION
    clock.advance(20 * DAY)
    assert fab.tick()["probation_failed"] == ["p"]


def test_clean_probation_becomes_canonical_at_ttl(fab, clock):
    make_canonical(fab, clock, "c")
    assert fab.atoms["c"].state_history[-1].actor == "system"


# ---------------------------------------------------------------- fix 9

def test_appeals_are_capped_and_the_second_decision_is_final(fab):
    fab.propose(atom("x"))
    fab.review("x", ALICE, "REJECT", "weak", fab.review_packet("x"))
    for n in (1, 2):
        fab.appeal("x", OWNER, [f"evidence {n}"], "please reconsider")
        with pytest.raises(NotAuthorized):
            fab.review("x", BOB, "REJECT", "no", fab.review_packet("x"))   # appeals need second line
        fab.review("x", DAN, "REJECT", "still weak", fab.review_packet("x"))
    assert fab.atoms["x"].appeal_final
    with pytest.raises(AppealRefused):
        fab.appeal("x", OWNER, ["more"], "again")
    assert check_invariants(fab) == []


# ------------------------------------------------------- authority rules

@pytest.mark.parametrize("who", ["pat", "agent-7"])
def test_no_self_approval(fab, who):
    fab.propose(atom("s"))
    with pytest.raises(SelfApproval):
        approve(fab, "s", Actor.of(who, Role.REVIEWER))


def test_automatic_review_cannot_decide_high(fab):
    fab.propose(atom("h", RiskTier.HIGH))
    with pytest.raises(NotAuthorized):
        approve(fab, "h", BOT)


def test_people_cannot_jump_to_canonical(fab):
    fab.propose(atom("j"))
    with pytest.raises(NotAuthorized):
        fab.transition("j", State.CANONICAL, ALICE, "trust me")


def test_rationale_and_legality_are_required(fab):
    fab.propose(atom("r"))
    with pytest.raises(TrustError):
        fab.transition("r", State.DEMOTED, ALICE, "  ")
    with pytest.raises(IllegalTransition):
        fab.transition("r", State.DISPUTED, ALICE, "proposed atoms are not disputed")


def test_stale_packet_when_blast_radius_grows(fab):
    fab.propose(atom("base"))
    packet = fab.review_packet("base")
    fab.propose(atom("dep", derived_from=("base",)))
    with pytest.raises(StaleReviewPacket):
        fab.review("base", ALICE, "APPROVE", "ok", packet)


def test_conflicts_are_shown_to_the_reviewer(fab):
    fab.propose(atom("k1", key="rate", content="4.5%"))
    fab.propose(atom("k2", key="rate", content="4.7%"))
    assert fab.review_packet("k2").conflicts == ("k1",)


def test_escalation_moves_to_regulatory_queue(fab):
    fab.propose(atom("e"))
    assert fab.review("e", ALICE, "ESCALATE", "touches a filing", fab.review_packet("e")) == "escalated"
    task = fab.reviews["e"]
    assert fab.atoms["e"].risk_tier is RiskTier.REGULATORY and task.dual_control and task.signatory_required


# --------------------------------------------- degraded mode, quarantine

def test_degraded_mode_only_quarantines_and_projection_labels_it(fab, clock):
    fab.propose(atom("late", RiskTier.MEDIUM))
    clock.advance(25 * 3600)
    assert fab.tick()["degraded_quarantine"] == ["late"]
    assert fab.atoms["late"].state is State.QUARANTINED
    manifest = project(fab)
    [entry] = [e for e in manifest.entries if e.atom_id == "late"]
    assert entry.weight == 0.3 and entry.label.startswith("UNVERIFIED")
    assert manifest.unlabeled_provisional() == []
    assert approve(fab, "late", ALICE) == "probation"      # the review still happens
    assert check_invariants(fab) == []


def test_quarantine_expires_to_demoted(fab, clock):
    fab.propose(atom("q"))
    clock.advance(73 * 3600)
    fab.tick()
    clock.advance(14 * DAY)
    assert fab.tick()["quarantine_expired"] == ["q"]


# ----------------------------------------------- cascade side effects

def test_summary_must_carry_lineage(fab):
    with pytest.raises(TrustError):
        fab.propose(atom("sum", kind="summary"))


def test_production_use_case_blocks_until_revalidated(fab, clock):
    make_canonical(fab, clock, "f")
    fab.register_use_case(UseCase("pricing", owner="uma", depends_on=frozenset({"f"}), in_production=True))
    manifest = fab.transition("f", State.DEMOTED, ALICE, "wrong")
    assert manifest.production_use_cases == ("pricing",)
    assert fab.blocked("pricing")
    with pytest.raises(NotAuthorized):
        fab.resolve_revalidation("pricing", "acknowledged", BOB)
    fab.resolve_revalidation("pricing", "re-derived", Actor.of("uma", Role.USE_CASE_OWNER))
    assert not fab.blocked("pricing")


def test_failed_delivery_does_not_block_demotion_or_lose_the_notice(fab, clock):
    make_canonical(fab, clock, "f")
    fab.register_use_case(UseCase("ops", owner="uma", depends_on=frozenset({"f"})))
    fab.transition("f", State.DEMOTED, ALICE, "wrong")
    assert fab.atoms["f"].state is State.DEMOTED

    def down(note):
        raise ConnectionError("mail relay down")

    assert fab.deliver_notifications(down) == 0
    [note] = fab.outbox
    assert not note.delivered and "mail relay down" in note.last_error
    assert fab.deliver_notifications(lambda n: None) == 1 and note.attempts == 2


def test_retro_review_deadline_is_tracked(fab, clock):
    make_canonical(fab, clock, "f")
    fab.register_use_case(UseCase("u", owner="uma", depends_on=frozenset({"f"}), in_production=True))
    fab.retroactive_demote("f", ALICE, "audit finding")
    clock.advance(2 * DAY + 1)
    assert [r.use_case_id for r in fab.overdue_retro_reviews()] == ["u"]


# ------------------------------------------------- retroactive demotion

def test_long_canonical_demotion_samples_outputs_in_its_window(fab, clock):
    make_canonical(fab, clock, "old")
    fab.record_output("before", ["old"], ts=clock() - 1)
    for i in range(20):
        clock.advance(2 * DAY)
        fab.record_output(f"o{i}", ["old"])
    fab.retroactive_demote("old", Actor.of("ic", Role.INCIDENT_COMMANDER), "bad upstream")
    sampled = [o for o, _ in fab.recheck_queue]
    assert sampled and "before" not in sampled and set(sampled) <= {f"o{i}" for i in range(20)}


def test_short_canonical_demotion_samples_nothing(fab, clock):
    make_canonical(fab, clock, "new")
    fab.record_output("o", ["new"])
    fab.retroactive_demote("new", ALICE, "typo")
    assert fab.recheck_queue == []


def test_retroactive_demotion_needs_an_authorised_role(fab, clock):
    make_canonical(fab, clock, "z")
    with pytest.raises(NotAuthorized):
        fab.retroactive_demote("z", Actor.of("rando", Role.SIGNATORY), "dislike")


# ------------------------------------------------ ledger and invariants

def test_ledger_chain_detects_tampering(fab, clock):
    make_canonical(fab, clock, "l")
    assert fab.ledger.verify() == []
    next(iter(fab.ledger)).body["proposer"] = "someone else"
    assert fab.ledger.verify()


def test_invariants_catch_a_direct_write(fab):
    fab.propose(atom("forged"))
    fab.atoms["forged"].state = State.CANONICAL      # bypasses every rule
    assert any("without an approval record" in p for p in check_invariants(fab))


# -------------------------------------------------------------- metrics

def test_metrics_from_records(fab, clock):
    fab.propose(atom("m1"))
    clock.advance(100)
    fab.propose(atom("m2"))
    assert metrics.promotion_backlog_age_p95(fab) == 100
    approve(fab, "m1", ALICE)
    fab.raise_dispute("m1", BOB, "wrong")
    assert metrics.reviewer_overturn_rate(fab) == {"alice": 1.0}
    fab.record_citation("m2", as_fact=True)
    assert metrics.quarantine_leak_rate(fab) == 1.0
    assert metrics.cascade_latency(fab) == [0]


def test_consolidate_proposes_only_above_threshold(fab):
    tasks = consolidate(fab, [atom("hi", confidence=0.9), atom("lo", confidence=0.2)], "s1", promote_min=0.8)
    assert [t.atom_id for t in tasks] == ["hi"]
    assert fab.atoms["hi"].state is State.PROPOSED and "lo" not in fab.atoms

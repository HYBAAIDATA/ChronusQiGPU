"""Formal learning: what to look for, how learning is judged, and what is known.

Every intelligence here learns from evidence: the world model fits the route
and the invalidation rate, the discovery engine builds a theory from its
experiments. This module is the part that *judges* the learning, the way a
teacher does, and it gives the learners their questions.

**Questions come first.** A learner that is not told what to look for will
not find it, however capable (Popper's "Observe!" has no answer without a
question). The questions are seeded from ``seeds/questions.yaml``: a
reviewed, human-readable file saying what each intelligence should look
for, why it matters, and what it must beat. They are published to the
knowledge fabric, so every intelligence can see what is being asked.

**Learning is judged prequentially** (Dawid, 1984). A learner commits its
forecast before the outcome is known and is scored only on outcomes it had
not yet seen, with a proper scoring rule (the log score), against a named
null forecaster committed at the same moment. The mean score difference is
the learning, in bits per outcome: zero means nothing has been learned that
the null did not already know. Its running sum is the log-likelihood ratio
of learner over null, the weight of evidence that learning happened.

**Status is earned and can be lost** (Dweck's "not yet"):

- ``open``: nobody has answered yet;
- ``not_yet``: forecasts are coming in, skill is not yet established;
- ``mastered``: the lower 95% bound of skill is above zero over the whole
  record *and* the recent record is still positive;
- ``regressed``: was mastered, but the recent record has fallen to zero or
  below (the world moved, or the learner forgot): back to learning.

Mastered knowledge keeps being tested on every new outcome (retrieval
practice); the recent record weighs new outcomes more than old ones, so
forgetting and drift show up as regression, not as silent error.

**Laws are exposed to refutation.** Some questions have a proven answer:
SHA-256d is modelled as a random oracle, so shares follow the work done,
``Poisson(hashes x (target + 1) / 2^256)``, whatever order nonces are tried
in. Such a law is tested on every window; its status is ``holds`` while the
exact (Garwood) 95% interval of observed/expected contains 1, and
``anomaly`` when it does not. An anomaly is a bug or a discovery, and needs
replication before anyone believes either; nothing acts on it automatically.

**Every result is explained** (Michie's strong criterion for machine
learning): each status carries a sentence an operator can read and act on.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "pythia.questions/1"
KINDS = ("quantity", "probability", "law", "fact", "open")
DEFAULT_SEEDS = Path(__file__).resolve().parent / "seeds" / "questions.yaml"
_LN2 = math.log(2.0)
_Z90 = 1.6448536269514722
_Z95 = 1.959963984540054
_P_FLOOR = 1e-6


@dataclass(frozen=True)
class Question:
    id: str
    ask: str
    why: str
    kind: str
    learner: str | None = None
    baseline: str | None = None  # the null forecaster, in words
    law: str | None = None
    answered_by: dict | None = None
    how: str | None = None
    min_n: int = 30
    recent_half_life: float = 100.0

    def as_dict(self) -> dict[str, Any]:
        return {
            k: v
            for k, v in {
                "id": self.id,
                "ask": self.ask,
                "why": self.why,
                "kind": self.kind,
                "learner": self.learner,
                "baseline": self.baseline,
                "law": self.law,
                "answered_by": self.answered_by,
                "how": self.how,
            }.items()
            if v is not None
        }


def load_questions(path: str | Path = DEFAULT_SEEDS) -> list[Question]:
    """The seeded questions; a malformed seed is refused, never half-loaded."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema") != SCHEMA:
        raise ValueError(f"{path}: schema must be {SCHEMA}")
    allowed = set(Question.__dataclass_fields__)
    questions: list[Question] = []
    for entry in raw.get("questions") or []:
        unknown = set(entry) - allowed
        if unknown:
            raise ValueError(f"{entry.get('id')}: unknown keys {sorted(unknown)}")
        q = Question(**entry)
        if q.kind not in KINDS:
            raise ValueError(f"{q.id}: kind must be one of {KINDS}")
        if q.kind in ("quantity", "probability") and not (q.learner and q.baseline):
            raise ValueError(f"{q.id}: a {q.kind} question needs a learner and a baseline")
        if q.kind == "law" and not q.law:
            raise ValueError(f"{q.id}: a law question states its law")
        if q.kind == "fact" and not (q.answered_by and q.answered_by.get("topic")):
            raise ValueError(f"{q.id}: a fact question names the topic that answers it")
        if not q.ask.strip() or not q.why.strip():
            raise ValueError(f"{q.id}: every question says what it asks and why")
        questions.append(q)
    ids = [q.id for q in questions]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{path}: duplicate question ids")
    return questions


def gaussian_bits(x: float, mu: float, sigma: float) -> float:
    """Log score of ``x`` under N(mu, sigma), in bits (lower is better)."""
    sigma = max(sigma, 1e-9)
    return (0.5 * math.log(2 * math.pi * sigma * sigma) + (x - mu) ** 2 / (2 * sigma**2)) / _LN2


def bernoulli_bits(happened: bool, p: float) -> float:
    """Log score of an event forecast with probability ``p``, in bits."""
    p = min(1.0 - _P_FLOOR, max(_P_FLOOR, p))
    return -math.log2(p if happened else 1.0 - p)


class ResidualScale:
    """A forecaster's own predictive spread: the RMS of its past errors.

    Each forecaster is judged with the spread its own record earns, so
    neither the learner nor the null is flattered by a borrowed one.
    """

    def __init__(self, initial: float = 0.5, floor: float = 0.01, half_life: float = 50.0):
        self.initial, self.floor = initial, floor
        self.decay = 0.5 ** (1.0 / half_life)
        self.w = self.sq = 0.0
        self.n = 0

    @property
    def sigma(self) -> float:
        if self.n < 5:
            return self.initial
        return max(self.floor, math.sqrt(self.sq / self.w))

    def observe(self, error: float) -> None:
        self.w = self.w * self.decay + 1.0
        self.sq = self.sq * self.decay + error * error
        self.n += 1


@dataclass
class _Record:
    n: int = 0
    s1: float = 0.0  # sum of (null - learner) bits
    s2: float = 0.0
    rw: float = 0.0  # exponentially weighted recent record
    rs: float = 0.0
    ever_mastered: bool = False
    covered: int = 0  # outcomes inside the learner's 90% interval
    interval_n: int = 0
    expected: float = 0.0  # law questions: expected and observed counts
    observed: int = 0

    def state(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


class LearningLedger:
    """Questions, forecasts, scores and status; published to the fabric."""

    SOURCE = "learning.ledger"

    def __init__(
        self,
        questions: list[Question],
        fabric: Any = None,
        *,
        publish_every_s: float = 300.0,
        clock=time.monotonic,
    ) -> None:
        self.questions = {q.id: q for q in questions}
        self.fabric = fabric
        self.publish_every_s = publish_every_s
        self._clock = clock
        self._records = {q.id: _Record() for q in questions}
        self._published_at = float("-inf")
        self._published_status: dict[str, str] = {}
        if fabric is not None:
            self._restore()
            for q in questions:
                fabric.publish(self.SOURCE, f"question.{q.id}", q.as_dict(), evidence="declared")

    @classmethod
    def from_seeds(cls, path: str | Path = DEFAULT_SEEDS, **kwargs: Any) -> "LearningLedger":
        return cls(load_questions(path), **kwargs)

    # ------------------------------------------------------------ evidence
    def score(self, qid: str, learner_bits: float, null_bits: float) -> None:
        """One outcome: each forecaster's log score, committed before it."""
        q, r = self.questions[qid], self._records[qid]
        diff = null_bits - learner_bits
        r.n += 1
        r.s1 += diff
        r.s2 += diff * diff
        decay = 0.5 ** (1.0 / q.recent_half_life)
        r.rw = r.rw * decay + 1.0
        r.rs = r.rs * decay + diff
        if self._skill(r)["mastered"]:
            r.ever_mastered = True

    def score_quantity(
        self,
        qid: str,
        outcome: float,
        learner: tuple[float, float],
        null: tuple[float, float],
    ) -> None:
        """``learner`` and ``null`` are (mean, sigma) Gaussian forecasts."""
        r = self._records[qid]
        mu, sigma = learner
        r.interval_n += 1
        r.covered += int(abs(outcome - mu) <= _Z90 * sigma)
        self.score(qid, gaussian_bits(outcome, *learner), gaussian_bits(outcome, *null))

    def score_probability(self, qid: str, happened: bool, learner: float, null: float) -> None:
        self.score(qid, bernoulli_bits(happened, learner), bernoulli_bits(happened, null))

    def law(self, qid: str, *, expected: float, observed: int) -> None:
        """The law's running totals (expected and observed counts)."""
        r = self._records[qid]
        r.expected, r.observed = float(expected), int(observed)

    # ------------------------------------------------------------ judgement
    @staticmethod
    def _skill(r: _Record) -> dict[str, Any]:
        """Skill over the whole record and the recent one; needs ``r.n >= 1``."""
        mean = r.s1 / r.n
        var = max(0.0, r.s2 / r.n - mean * mean)
        se = math.sqrt(var / r.n) if r.n > 1 else float("inf")
        recent = r.rs / r.rw
        low, high = mean - _Z95 * se, mean + _Z95 * se
        return {
            "mean": mean,
            "low": low,
            "high": high,
            "recent": recent,
            "evidence_bits": r.s1,
            "mastered": r.n >= 2 and low > 0 and recent > 0,
        }

    def status(self, qid: str) -> dict[str, Any]:
        q, r = self.questions[qid], self._records[qid]
        base = {"id": q.id, "ask": q.ask, "kind": q.kind, "learner": q.learner}
        if q.kind in ("quantity", "probability"):
            return {**base, **self._judge(q, r)}
        if q.kind == "law":
            return {**base, **self._judge_law(q, r)}
        if q.kind == "fact":
            return {**base, **self._judge_fact(q)}
        return {
            **base,
            "status": "open",
            "explanation": f"open: no learner answers this yet. {q.how or ''}".strip(),
        }

    def _judge(self, q: Question, r: _Record) -> dict[str, Any]:
        if r.n == 0:
            return {
                "status": "open",
                "n": 0,
                "explanation": f"open: {q.learner} has made no forecast yet",
            }
        s = self._skill(r)
        if r.n < q.min_n:
            status = "not_yet"
        elif s["mastered"]:
            status = "mastered"
        elif r.ever_mastered and s["recent"] <= 0:
            status = "regressed"
        else:
            status = "not_yet"
        verdict = {
            "mastered": f"{q.learner} has learned this",
            "regressed": f"{q.learner} had learned this, but its recent forecasts no longer beat its baseline: re-learning",
            "not_yet": (
                f"not yet: {r.n} of {q.min_n} outcomes needed"
                if r.n < q.min_n
                else f"not yet: {q.learner} does not reliably beat its baseline"
            ),
        }[status]
        explanation = (
            f"{verdict}. Over {r.n} outcomes it scores {s['mean']:+.3f} bits per outcome "
            f"against {q.baseline} (95% interval {s['low']:+.3f} to {s['high']:+.3f}; "
            f"recent {s['recent']:+.3f})."
        )
        out: dict[str, Any] = {
            "status": status,
            "n": r.n,
            "skill_bits": s["mean"],
            "skill_ci95": [s["low"], s["high"]],
            "recent_bits": s["recent"],
            "evidence_bits": s["evidence_bits"],
        }
        if r.interval_n:
            coverage = r.covered / r.interval_n
            out["coverage90"] = coverage
            calibration = (
                "calibrated"
                if r.interval_n < 50 or 0.8 <= coverage <= 0.97
                else "overconfident" if coverage < 0.8 else "underconfident"
            )
            out["calibration"] = calibration
            explanation += f" Its 90% intervals held {coverage:.0%} of outcomes ({calibration})."
        out["explanation"] = explanation
        return out

    def _judge_law(self, q: Question, r: _Record) -> dict[str, Any]:
        from .mining.hashrate_governor import poisson_interval

        if r.expected <= 0:
            return {"status": "open", "explanation": f"open: no work yet to test {q.law}"}
        low, high = poisson_interval(r.observed)
        ratio = r.observed / r.expected
        ci = [low / r.expected, high / r.expected]
        holds = ci[0] <= 1.0 <= ci[1]
        status = "holds" if holds else "anomaly"
        explanation = (
            f"{q.law}: {r.observed} observed against {r.expected:.3f} expected "
            f"(ratio {ratio:.3f}, exact 95% interval {ci[0]:.3f} to {ci[1]:.3f}). "
            + (
                "The law holds."
                if holds
                else "ANOMALY: a bug or a discovery; replicate before believing either."
            )
        )
        return {
            "status": status,
            "observed": r.observed,
            "expected": r.expected,
            "ratio": ratio,
            "ci95": ci,
            "explanation": explanation,
        }

    def _judge_fact(self, q: Question) -> dict[str, Any]:
        spec = q.answered_by or {}
        fact = self.fabric.observe(spec["topic"]) if self.fabric is not None else None
        value: Any = None if fact is None else fact.value
        for key in spec.get("path", []):
            value = value.get(key) if isinstance(value, dict) else None
        if fact is None or value is None:
            return {"status": "open", "explanation": f"open: nothing on {spec['topic']} yet"}
        stale = self.fabric.stale(fact)
        return {
            "status": "stale" if stale else "answered",
            "answer": value,
            "fact_id": fact.fact_id,
            "explanation": (
                f"answered by {fact.source} ({fact.evidence}): {value}"
                + (" -- its basis has changed; awaiting a new answer" if stale else "")
            ),
        }

    def report(self) -> dict[str, Any]:
        return {
            "schema": "pythia.learning/1",
            "questions": [self.status(qid) for qid in self.questions],
        }

    # ------------------------------------------------------------ sharing
    def publish(self, force: bool = False) -> int:
        """Publish statuses; on a status change at once, otherwise periodically."""
        if self.fabric is None:
            return 0
        now = self._clock()
        due = force or now - self._published_at >= self.publish_every_s
        published = 0
        for qid in self.questions:
            status = self.status(qid)
            changed = self._published_status.get(qid) != status["status"]
            if not (due or changed):
                continue
            value = _json_safe({**status, "state": self._records[qid].state()})
            self.fabric.publish(self.SOURCE, f"learning.{qid}", value, evidence="measured")
            self._published_status[qid] = status["status"]
            published += 1
        if due:
            self._published_at = now
        return published

    def _restore(self) -> None:
        """Learning survives restarts: the last published record is the state."""
        for qid, record in self._records.items():
            fact = self.fabric.observe(f"learning.{qid}", source=self.SOURCE)
            state = (fact.value or {}).get("state") if fact is not None else None
            if not isinstance(state, dict):
                continue
            for key in record.__dataclass_fields__:
                if key in state:
                    setattr(record, key, type(getattr(record, key))(state[key]))
            self._published_status[qid] = fact.value.get("status")


def _json_safe(value: Any) -> Any:
    """Round floats to 6 significant figures; infinities become None."""
    if isinstance(value, float):
        return float(f"{value:.6g}") if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value

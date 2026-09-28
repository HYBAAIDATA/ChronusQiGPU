"""Knowledge fabric: what one intelligence learns, every intelligence can know.

Each intelligence (the mining world model and operating policy, the
hashrate governor, Salamander's recovery authority, the discovery engine,
the skills Salamander has grafted) publishes *facts*: a topic, a JSON value,
the class of evidence behind it, and the facts it was derived from. Any
other intelligence can observe the latest fact on a topic or subscribe to
a topic pattern.

Entanglement is non-separable knowledge. A fact derived from another
intelligence's fact is bound to it: when the source is superseded, every
fact bound to it, transitively, decoheres at once (it is marked stale and
subscribers are told), so no intelligence acts on knowledge whose basis
has changed. The joint state has one digest over every current fact and
its coherence; two intelligences holding the same digest know they share
the same world.

Across processes the fabric is a journal: one JSON line per fact, each
carrying the SHA-256 of the line before it, appended under a file lock
and replayed by every reader. A broken chain is refused, never repaired.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    import fcntl
except ImportError:  # Windows: single-process use only.
    fcntl = None

EVIDENCE = ("measured", "computed", "simulated", "declared")
GENESIS = "0" * 64


def default_journal_path() -> Path:
    """One journal for every process: beside the intelligence's Aethel memory."""
    configured = os.getenv("PYTHIA_INTELLIGENCE_DIR", "").strip()
    base = (
        Path(configured)
        if configured
        else Path(__file__).resolve().parents[3] / "data" / "intelligence"
    )
    return base.resolve() / "knowledge.jsonl"


def _canonical(value: Any) -> str:
    # Strict JSON: a value that cannot round-trip exactly would mean one
    # thing in memory and another in the journal.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class JournalCorrupted(RuntimeError):
    """The journal's hash chain does not verify; nothing past the break is trusted."""


@dataclass(frozen=True)
class Fact:
    fact_id: str
    source: str
    topic: str
    version: int
    value: Any
    evidence: str
    depends_on: tuple[str, ...]
    at: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "source": self.source,
            "topic": self.topic,
            "version": self.version,
            "value": self.value,
            "evidence": self.evidence,
            "depends_on": list(self.depends_on),
            "at": self.at,
        }

    @staticmethod
    def make(source, topic, version, value, evidence, depends_on, at) -> "Fact":
        body = {
            "source": source,
            "topic": topic,
            "version": version,
            "value": value,
            "evidence": evidence,
            "depends_on": sorted(depends_on),
            "at": at,
        }
        fact_id = hashlib.sha256(_canonical(body).encode()).hexdigest()
        return Fact(fact_id, source, topic, version, value, evidence, tuple(sorted(depends_on)), at)


Listener = Callable[[str, Fact], None]


class KnowledgeFabric:
    def __init__(self, journal: str | os.PathLike[str] | None = None, *, clock=time.time) -> None:
        self.journal = Path(journal) if journal is not None else None
        self._clock = clock
        self._lock = threading.RLock()
        self.facts: dict[str, Fact] = {}
        self._current: dict[tuple[str, str], str] = {}  # (source, topic) -> fact id
        self._superseded: set[str] = set()
        self._stale: set[str] = set()
        self._dependents: dict[str, set[str]] = {}
        self._listeners: list[tuple[str, Listener]] = []
        self._offset = 0
        self._head = GENESIS
        self.integrity_error: str | None = None
        if self.journal is not None:
            self.sync()

    # ------------------------------------------------------------ writing
    def publish(
        self,
        source: str,
        topic: str,
        value: Any,
        *,
        evidence: str,
        depends_on: Iterable[str | Fact] = (),
    ) -> Fact:
        """Publish ``value`` as ``source``'s knowledge of ``topic``.

        Republishing an unchanged value and basis returns the current fact.
        A new value supersedes the old one and decoheres its dependents.
        """
        if evidence not in EVIDENCE:
            raise ValueError(f"evidence must be one of {EVIDENCE}")
        if not source or not topic:
            raise ValueError("source and topic are required")
        deps = tuple(sorted(d.fact_id if isinstance(d, Fact) else d for d in depends_on))
        if json.loads(_canonical(value)) != value:
            raise TypeError("fact values must be plain JSON (dict keys as strings, no tuples)")
        with self._lock, self._journal_lock():
            self._read_journal()
            for dep in deps:
                if dep not in self.facts:
                    raise ValueError(f"cannot bind to unknown fact {dep[:12]}")
            current_id = self._current.get((source, topic))
            if current_id is not None:
                current = self.facts[current_id]
                if (
                    _canonical(current.value) == _canonical(value)
                    and current.depends_on == deps
                    and current_id not in self._stale
                ):
                    return current
            version = 1 if current_id is None else self.facts[current_id].version + 1
            fact = Fact.make(source, topic, version, value, evidence, deps, self._clock())
            self._append(fact)
            events = self._apply(fact)
        self._notify(events)
        return fact

    # ------------------------------------------------------------ reading
    def observe(self, topic: str, *, source: str | None = None) -> Fact | None:
        """The latest current fact on ``topic`` (from ``source`` if given)."""
        with self._lock:
            candidates = [
                self.facts[fid]
                for (src, top), fid in self._current.items()
                if top == topic and (source is None or src == source)
            ]
        return max(candidates, key=lambda f: f.at, default=None)

    def stale(self, fact: Fact | str) -> bool:
        """True once anything this fact was derived from has been superseded."""
        fid = fact.fact_id if isinstance(fact, Fact) else fact
        return fid in self._stale

    def subscribe(self, pattern: str, listener: Listener) -> Callable[[], None]:
        """``listener(event, fact)`` for topics matching ``pattern``;
        events are "published" and "decohered"."""
        entry = (pattern, listener)
        with self._lock:
            self._listeners.append(entry)

        def unsubscribe() -> None:
            with self._lock:
                if entry in self._listeners:
                    self._listeners.remove(entry)

        return unsubscribe

    def sync(self) -> int:
        """Replay facts other processes appended; returns how many arrived."""
        if self.journal is None or not self.journal.exists():
            return 0
        with self._lock, self._journal_lock(shared=True):
            events = self._read_journal()
        self._notify(events)
        return sum(1 for event, _ in events if event == "published")

    def joint_digest(self) -> str:
        with self._lock:
            state = sorted((fid, fid in self._stale) for fid in self._current.values())
        return hashlib.sha256(_canonical(state).encode()).hexdigest()

    def snapshot(self, *, recent: int = 20) -> dict[str, Any]:
        with self._lock:
            current = [self.facts[fid] for fid in self._current.values()]
            latest = sorted(self.facts.values(), key=lambda f: f.at)[-recent:]
            return {
                "schema": "pythia.knowledge/1",
                "joint_digest": self.joint_digest(),
                "facts": len(self.facts),
                "current": len(current),
                "stale": sum(1 for f in current if f.fact_id in self._stale),
                "sources": sorted({f.source for f in current}),
                "topics": sorted({f.topic for f in current}),
                "integrity_error": self.integrity_error,
                "recent": [
                    {**f.as_dict(), "stale": f.fact_id in self._stale} for f in reversed(latest)
                ],
            }

    # ------------------------------------------------------------ internals
    def _apply(self, fact: Fact) -> list[tuple[str, Fact]]:
        events = [("published", fact)]
        self.facts[fact.fact_id] = fact
        for dep in fact.depends_on:
            self._dependents.setdefault(dep, set()).add(fact.fact_id)
        previous = self._current.get((fact.source, fact.topic))
        self._current[(fact.source, fact.topic)] = fact.fact_id
        if fact.depends_on and any(
            d in self._superseded or d in self._stale for d in fact.depends_on
        ):
            self._stale.add(fact.fact_id)
        if previous is not None and previous != fact.fact_id:
            self._superseded.add(previous)
            events.extend(self._decohere(previous))
        return events

    def _decohere(self, root: str) -> list[tuple[str, Fact]]:
        events, frontier = [], [root]
        while frontier:
            for child in self._dependents.get(frontier.pop(), ()):
                if child not in self._stale:
                    self._stale.add(child)
                    events.append(("decohered", self.facts[child]))
                    frontier.append(child)
        return events

    def _notify(self, events: list[tuple[str, Fact]]) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for event, fact in events:
            for pattern, listener in listeners:
                if fnmatch.fnmatchcase(fact.topic, pattern):
                    listener(event, fact)

    def _journal_lock(self, *, shared: bool = False):
        fabric = self

        class _Lock:
            def __enter__(self_inner):
                self_inner.fh = None
                if fabric.journal is None:
                    return self_inner
                fabric.journal.parent.mkdir(parents=True, exist_ok=True)
                self_inner.fh = open(fabric.journal, "a+", encoding="utf-8")
                if fcntl is not None:
                    fcntl.flock(self_inner.fh, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
                return self_inner

            def __exit__(self_inner, *exc):
                if self_inner.fh is not None:
                    if fcntl is not None:
                        fcntl.flock(self_inner.fh, fcntl.LOCK_UN)
                    self_inner.fh.close()
                return False

        return _Lock()

    def _read_journal(self) -> list[tuple[str, Fact]]:
        if self.journal is None or not self.journal.exists() or self.integrity_error:
            return []
        events: list[tuple[str, Fact]] = []
        with open(self.journal, "r", encoding="utf-8") as fh:
            fh.seek(self._offset)
            while True:
                line = fh.readline()
                if not line or not line.endswith("\n"):
                    break  # nothing more, or a line still being written
                try:
                    record = json.loads(line)
                    body = record["fact"]
                    if record["prev"] != self._head:
                        raise JournalCorrupted("chain break: prev does not match")
                    digest = hashlib.sha256(
                        (record["prev"] + _canonical(body)).encode()
                    ).hexdigest()
                    if digest != record["digest"]:
                        raise JournalCorrupted("chain break: digest does not match")
                    fact = Fact(
                        body["fact_id"],
                        body["source"],
                        body["topic"],
                        body["version"],
                        body["value"],
                        body["evidence"],
                        tuple(body["depends_on"]),
                        body["at"],
                    )
                    rebuilt = Fact.make(
                        fact.source,
                        fact.topic,
                        fact.version,
                        fact.value,
                        fact.evidence,
                        fact.depends_on,
                        fact.at,
                    )
                    if rebuilt.fact_id != fact.fact_id:
                        raise JournalCorrupted("fact id does not match its content")
                except (ValueError, KeyError, JournalCorrupted) as exc:
                    self.integrity_error = f"{self.journal}@{self._offset}: {exc}"
                    break
                self._offset = fh.tell()
                self._head = record["digest"]
                if fact.fact_id not in self.facts:
                    events.extend(self._apply(fact))
        return events

    def _append(self, fact: Fact) -> None:
        if self.journal is None:
            return
        if self.integrity_error:
            raise JournalCorrupted(self.integrity_error)
        body = fact.as_dict()
        digest = hashlib.sha256((self._head + _canonical(body)).encode()).hexdigest()
        line = _canonical({"prev": self._head, "digest": digest, "fact": body}) + "\n"
        with open(self.journal, "a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        # Our own line is part of the chain we have read.
        self._offset = self.journal.stat().st_size
        self._head = digest

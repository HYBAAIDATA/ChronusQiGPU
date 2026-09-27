"""Tests for the PYTHIA persistent store.

Covers: run journal (every run logged + fed back), qudit memory traces
(store in qudits, retrieve by fidelity), disk snapshots (memory survives
restarts), and autonomous curation (she decides what to keep and prune).
"""

import sys
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from Intelligence.pythia_learning import PythiaLearning
from Intelligence.pythia_memory import PythiaMemorySystem
from Intelligence.pythia_store import (
    PythiaStore,
    QuditMemoryStore,
    RunJournal,
)


class TestRunJournal(unittest.TestCase):
    def test_append_and_readback(self):
        with tempfile.TemporaryDirectory() as d:
            j = RunJournal(Path(d) / "journal.jsonl")
            j.append("experiment", {"run": 1, "score": 0.5})
            j.append("teach", {"patterns": 3})
            self.assertEqual(j.count(), 2)
            entries = j.entries()
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0]["kind"], "experiment")
            self.assertEqual(entries[1]["payload"]["patterns"], 3)
            self.assertEqual(entries[1]["seq"], 1)
            # Filter by kind.
            self.assertEqual(len(j.entries(kind="teach")), 1)
            # A new journal over the same file sees the prior entries.
            j2 = RunJournal(Path(d) / "journal.jsonl")
            self.assertEqual(j2.count(), 2)

    def test_tail_as_patterns_feeds_ai(self):
        with tempfile.TemporaryDirectory() as d:
            j = RunJournal(Path(d) / "journal.jsonl")
            for i in range(5):
                j.append("experiment", {"run": i})
            patterns = j.tail_as_patterns(limit=4, n_units=32)
            self.assertEqual(len(patterns), 4)
            for p in patterns:
                self.assertEqual(p.shape, (32,))
            # Deterministic: same journal -> same vectors.
            again = j.tail_as_patterns(limit=4, n_units=32)
            for a, b in zip(patterns, again):
                np.testing.assert_allclose(a, b)


class TestQuditMemoryStore(unittest.TestCase):
    def test_store_and_retrieve_by_fidelity(self):
        q = QuditMemoryStore(dim=32)
        q.store("a", [1.0, 0.0, 0.5])
        q.store("b", [0.0, 9.0, -1.0])
        res = q.retrieve([1.0, 0.0, 0.5])
        self.assertTrue(res)
        top_trace, top_fidelity = res[0]
        self.assertEqual(top_trace.key, "a")
        self.assertGreater(top_fidelity, 0.9)
        self.assertGreater(top_fidelity, res[1][1])

    def test_snapshot_roundtrip_preserves_states(self):
        q = QuditMemoryStore(dim=32)
        q.store("a", [0.25, 0.5, 0.75])
        original = q.retrieve([0.25, 0.5, 0.75])[0][1]
        snap = q.to_snapshot()
        q2 = QuditMemoryStore(dim=32)
        q2.load_snapshot(snap)
        restored = q2.retrieve([0.25, 0.5, 0.75])[0][1]
        self.assertAlmostEqual(original, restored, places=12)


class TestPersistence(unittest.TestCase):
    def _seed_memory(self, mem: PythiaMemorySystem, pyth: PythiaLearning):
        mem.episodic.record(
            trigger="mining cycle 1",
            plan=["toe", "guide", "verify"],
            tool_calls=[{"tool": "guide_mining"}],
            outcome={"winner": 42},
            reward=1.0,
        )
        mem.semantic.add_concept(
            "zeckendorf_schedule",
            category="mining_primitive",
            definition="Fibonacci-spaced nonce schedule",
            provenance="seed",
        )
        # Repeatedly teach the same success-linked pattern -> germ-line.
        strong = np.linspace(0.0, 1.0, 32)
        pyth.learning_step([strong] * 5, [True] * 5)

    def test_memory_survives_restart(self):
        with tempfile.TemporaryDirectory() as d:
            mem = PythiaMemorySystem()
            pyth = PythiaLearning()
            store = PythiaStore(mem, pyth, store_dir=Path(d))
            self._seed_memory(mem, pyth)
            n_events = mem.episodic.status()["n_events"]
            n_concepts = mem.semantic.status()["n_concepts"]
            n_lt = pyth.status()["long_term_memories"]
            store.save()

            mem2 = PythiaMemorySystem()
            pyth2 = PythiaLearning()
            store2 = PythiaStore(mem2, pyth2, store_dir=Path(d))
            self.assertTrue(store2.load())
            self.assertEqual(mem2.episodic.status()["n_events"], n_events)
            self.assertEqual(mem2.semantic.status()["n_concepts"], n_concepts)
            self.assertEqual(pyth2.status()["long_term_memories"], n_lt)
            # Content is actually intact.
            self.assertIsNotNone(mem2.semantic._nodes.get("zeckendorf_schedule"))
            self.assertGreater(store2.qudits.status()["n_traces"], 0)

    def test_ingest_feeds_journal_to_learning(self):
        with tempfile.TemporaryDirectory() as d:
            mem = PythiaMemorySystem()
            pyth = PythiaLearning()
            store = PythiaStore(mem, pyth, store_dir=Path(d))
            for i in range(6):
                store.record_run("experiment", {"run": i, "delta": i * 0.1})
            taught = store.ingest(limit=6)
            self.assertEqual(taught, 6)
            self.assertGreater(pyth.status()["long_term_memories"], 0)


class TestCuration(unittest.TestCase):
    def _build(self, d: str):
        mem = PythiaMemorySystem()
        pyth = PythiaLearning()
        store = PythiaStore(mem, pyth, store_dir=Path(d))
        return store, mem, pyth

    def test_she_prunes_weak_and_keeps_germ_line(self):
        with tempfile.TemporaryDirectory() as d:
            store, mem, pyth = self._build(d)
            # Strong success-linked pattern -> germ_line, high activation.
            strong = np.linspace(0.0, 1.0, 32)
            pyth.learning_step([strong] * 6, [True] * 6)
            # Weak somatic patterns: single activation, never retrieved.
            for i in range(12):
                pyth.learning_step([np.full(32, i * 0.037)], [False])
            # A stale, never-useful episode.
            stale = mem.episodic.record("stale run", [], [], {}, reward=0.0)
            stale.timestamp = time.time() - 10_000_000  # ~4 months old
            # A fresh, rewarded episode.
            mem.episodic.record("good run", ["plan"], [], {"ok": True}, reward=1.0)

            report = store.curate(emergence_signal=0.2)

            # Germ-line pattern must survive (her veto).
            surviving_fates = [m.cell_fate for m in pyth.patterns()]
            self.assertIn("germ_line", surviving_fates)
            # The stale episode should be gone.
            remaining_ids = {e.event_id for e in mem.episodic.events()}
            self.assertNotIn(stale.event_id, remaining_ids)
            # Every decision is reported and journaled.
            self.assertEqual(
                report["n_evaluated"], report["kept"] + report["demoted"] + report["pruned"]
            )
            self.assertGreater(report["demoted"] + report["pruned"], 0)
            curation_entries = store.journal.entries(kind="curation")
            self.assertEqual(len(curation_entries), 1)
            decisions = curation_entries[0]["payload"]["decisions"]
            self.assertTrue(all("reasons" in d for d in decisions))
            # Snapshot was written by curate().
            self.assertTrue(store.snapshot_path.is_file())

    def test_nothing_pruned_when_all_strong(self):
        with tempfile.TemporaryDirectory() as d:
            store, mem, pyth = self._build(d)
            strong = np.linspace(0.0, 1.0, 32)
            pyth.learning_step([strong] * 6, [True] * 6)
            report = store.curate(emergence_signal=0.5)
            # A single high-utility memory must never be pruned.
            self.assertEqual(report["pruned"], 0)
            self.assertEqual(pyth.status()["long_term_memories"], 1)


if __name__ == "__main__":
    unittest.main()

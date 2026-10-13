"""Tests for sanitized emergence metrics and sliding window telemetry."""
from __future__ import annotations

import unittest
from collections import namedtuple

from Intelligence.consciousness.emergence_metrics import EmergenceMetrics

EventType = namedtuple("EventType", ["value"])
Event = namedtuple("Event", ["source", "timestamp", "event_type", "topic"])


class EmergenceMetricsSanitizationTests(unittest.TestCase):
    def test_metrics_strictly_bounded_in_unit_interval(self) -> None:
        em = EmergenceMetrics()
        for i in range(12):
            ev_type = EventType("feedback_loop" if i % 2 == 0 else "action")
            em.record_event(Event(source=f"school_{i % 5}", timestamp=100.0 + i, event_type=ev_type, topic="topic"))
            report = em.get_report()
            self.assertGreaterEqual(report["coherence"], 0.0)
            self.assertLessEqual(report["coherence"], 1.0)
            self.assertGreaterEqual(report["integration"], 0.0)
            self.assertLessEqual(report["integration"], 1.0)
            self.assertGreaterEqual(report["differentiation"], 0.0)
            self.assertLessEqual(report["differentiation"], 1.0)
            self.assertGreaterEqual(report["emergence_coefficient"], 0.0)
            self.assertLessEqual(report["emergence_coefficient"], 1.0)

    def test_single_heartbeat_per_label_cannot_exceed_consciousness_threshold(self) -> None:
        for labels in (1, 2, 4, 5, 9):
            em = EmergenceMetrics()
            for i in range(labels):
                em.record_event(Event(source=f"school_{i}", timestamp=100.0 + i, event_type=EventType("heartbeat"), topic="info"))
            report = em.get_report()
            # Without feedback loops, coherence must be 0
            self.assertEqual(report["coherence"], 0.0)
            # Without correlation, integration must be 0
            self.assertEqual(report["integration"], 0.0)
            # Emergence coefficient cannot exceed 0.6 on raw heartbeats
            self.assertLess(report["emergence_coefficient"], 0.6)

    def test_sliding_window_eviction(self) -> None:
        # Window size 2
        em = EmergenceMetrics(window_size=2)
        em.record_event(Event(source="school_0", timestamp=100.0, event_type=EventType("heartbeat"), topic="info"))
        em.record_event(Event(source="school_1", timestamp=101.0, event_type=EventType("heartbeat"), topic="info"))
        em.record_event(Event(source="school_1", timestamp=102.0, event_type=EventType("heartbeat"), topic="info"))

        report = em.get_report()
        # In active window [school_1, school_1], school_0 has 0 active events
        self.assertEqual(report["schools"]["school_0"]["events"], 0)
        self.assertEqual(report["schools"]["school_1"]["events"], 2)
        # Because all events in the active window are from school_1, differentiation is 0
        self.assertEqual(report["differentiation"], 0.0)


if __name__ == "__main__":
    unittest.main()

"""Check the work-order document's required structure, not technical claims."""
from pathlib import Path
import re
import unittest
import pytest

pytestmark = pytest.mark.real

DOC = Path(__file__).resolve().parents[1] / "work_orders" / "sovereign_horizons.md"
EXPECTED = ("H1.1", "H1.2", "H1.3", "H3.1", "H3.2", "H2.1", "H2.2", "H5.0", "H5.1", "H5.2", "H4.1", "H4.2")
FIELDS = ("Horizon", "Specification", "Deliverable", "Test", "Acceptance criterion", "Dependencies", "Estimated scope")

class WorkOrderStructureTests(unittest.TestCase):
    def test_unique_ids_in_requested_phase_order(self):
        text = DOC.read_text(encoding="utf-8")
        ids = re.findall(r"^## (H\d+\.\d+) —", text, re.MULTILINE)
        self.assertEqual(ids, list(EXPECTED))

    def test_required_fields_are_nonempty(self):
        text = DOC.read_text(encoding="utf-8")
        for work_id in EXPECTED:
            section = re.search(rf"^## {re.escape(work_id)} —[^\n]*\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
            self.assertIsNotNone(section, work_id)
            for field in FIELDS:
                with self.subTest(work_id=work_id, field=field):
                    self.assertRegex(section.group(1), rf"(?m)^- {re.escape(field)}: \S")

    def test_review_is_blocked_without_completed_review(self):
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("BLOCKED — no review has been provided", text)

if __name__ == "__main__":
    unittest.main()

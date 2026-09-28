import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "strict_hardware_gate.py"
SPEC = importlib.util.spec_from_file_location("mla1517_strict_hardware_gate", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class StrictHardwareReportTests(unittest.TestCase):
    def test_report_writer_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "results" / "strict_hardware_gate.json"
            MODULE._write_report(report_path, {"status": "FAIL"})
            self.assertEqual(json.loads(report_path.read_text()), {"status": "FAIL"})


if __name__ == "__main__":
    unittest.main()

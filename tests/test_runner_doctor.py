"""Runner doctor fails closed on OneDrive work paths and bad Python pins."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "ci"))

import runner_doctor  # noqa: E402


class RunnerDoctorTests(unittest.TestCase):
    def test_onedrive_work_path_fails(self) -> None:
        fake = Path("/Users/leonn/OneDrive/Desktop/actions-runner/_work").resolve()
        with patch.dict(os.environ, {"GITHUB_WORKSPACE": str(fake)}, clear=False):
            with patch.object(runner_doctor, "_work_roots", return_value=[fake]):
                self.assertEqual(runner_doctor.main(), 1)

    def test_actions_requires_python_313(self) -> None:
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=False):
            with patch.object(runner_doctor.sys, "version_info", (3, 12, 3)):
                # Avoid OneDrive noise; stub roots to cwd.
                with patch.object(
                    runner_doctor, "_work_roots", return_value=[Path.cwd()]
                ):
                    self.assertEqual(runner_doctor.main(), 1)


if __name__ == "__main__":
    unittest.main()

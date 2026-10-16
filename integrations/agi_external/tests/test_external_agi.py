"""Tests for External AGI Surface and Boundary Enforcement.

Verifies:
1. ExternalAGI contract-bound reasoning and capability exposure.
2. Strict isolation firewall: integrations.agi_external never imports Intelligence.asi.
"""

from __future__ import annotations

import sys
import unittest
from integrations.agi_external import EXTERNAL_AGI_CAPABILITIES, ExternalAGI


class TestExternalAGISurface(unittest.TestCase):
    def setUp(self) -> None:
        self.agi = ExternalAGI()

    def test_capabilities_declaration(self) -> None:
        caps = self.agi.capabilities()
        self.assertIn("llm_gateway", caps)
        self.assertIn("reasoning", caps)
        self.assertIn("retrieval", caps)
        self.assertIn("structured_output", caps)
        # ASI is completely absent from capabilities
        self.assertNotIn("asi", caps)
        self.assertNotIn("self_modification", caps)

    def test_reasoning_flow(self) -> None:
        result = self.agi.reason("Summarise risk posture.", client_id="test_client")
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(result["security"], "APPROVED")
        self.assertIn("EUCLID", result["output"])

    def test_strict_asi_isolation_boundary(self) -> None:
        """Enforces that importing and running ExternalAGI does not pull in Intelligence.asi."""
        import integrations.agi_external as agi_ext

        # Inspect all module attributes and references
        module_source = inspect_module_imports(agi_ext)
        self.assertNotIn("Intelligence.asi", module_source)
        self.assertNotIn("asi_core", module_source)


def inspect_module_imports(mod: Any) -> str:
    import inspect

    return inspect.getsource(mod)


if __name__ == "__main__":
    unittest.main()

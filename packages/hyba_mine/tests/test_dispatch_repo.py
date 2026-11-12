# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Fleet dispatch adapter, product separation and repository hygiene."""

import ast
import asyncio
import importlib
import json
import re
import sys
import unittest
from pathlib import Path

import _support  # noqa: F401  (import paths)
from _support import PACKAGE_ROOT, REPO_ROOT

from chronus.stratum.gatekeeper import decode_nbits_target

from hyba_mine.dispatch import DispatchError, FleetDispatcher, LocalIGPUDispatcher, load_fleet_executor
from hyba_mine.igpu import ROUTE_MODE_A, BackendRoute, ModeALane
from hyba_mine.plan import NoncePlan
from hyba_mine.pools import POOL_CATALOG
from hyba_mine.vectors import GENESIS
from hyba_mine.work import check_result_integrity, make_device_unit

COPYRIGHT = "Copyright (c) 2026 HYBA Software Ltd. All rights reserved."


def _fleet_present() -> bool:
    try:
        importlib.import_module("chronus.fleet.executor")
    except ImportError:
        return False
    return True


FLEET = _fleet_present()


class FakeFleet:
    """Implements the fleet's public interface exactly: submit(chronus.fleet.WorkUnit, timeout) -> FleetResult."""

    def __init__(self, tamper=None):
        self.units = []
        self.tamper = tamper

    def submit(self, unit, timeout=None):
        from chronus.fleet.executor import FleetResult
        from chronus.fleet.kernels import default_registry
        from chronus.fleet.receipts import ReceiptCheck

        self.units.append(unit)
        kernel = default_registry(plugins=["hyba_mine.fleet_kernel"]).get(unit.kernel, unit.kernel_version)
        prepared = kernel.prepare(unit.params, unit.payload)
        cut = prepared.items // 2
        outputs = [kernel.run_reference(None, prepared.params, unit.payload, a, b)
                   for a, b in ((0, cut), (cut, prepared.items))]
        output = kernel.merge(prepared.params, outputs)
        receipt = {
            "receipt_id": "0" * 64,
            "work_unit": {"digest": unit.digest()},
            "routes": {"requested": unit.route, "executed_tiles": {"igpu": 2}},
            "devices": [{"label": "imac", "exec_ns": 1_000_000}],
            "backend": {"requested_backend": unit.route, "preference": unit.prefer or "each worker's --prefer",
                        "executed_backends": {"igpu": 2}},
            "tier": {"entitlement": {"label": "Tier 1"}},
        }
        if self.tamper:
            output, receipt = self.tamper(output, receipt)
        return FleetResult("job-0000000000000001", output, receipt, ReceiptCheck(True))


def _unit():
    plan = NoncePlan.for_header(GENESIS.prefix)
    position = plan.position_of(GENESIS.nonce)
    return make_device_unit(plan, position - position % plan.lane_size, plan.lane_size,
                            decode_nbits_target(GENESIS.nbits), "fleet")


ROUTE = BackendRoute("auto", ROUTE_MODE_A, None, "auto", "ours", ("igpu",), "igpu")


@unittest.skipUnless(FLEET, "chronus.fleet is not installed in this tree")
class TestFleetAdapter(unittest.TestCase):
    def test_the_plugin_kernel_passes_the_fleet_contract(self):
        from chronus.fleet.adapters import IGPUAdapter, ReferenceAdapter
        from chronus.fleet.kernels import KernelRegistry, default_registry

        from hyba_mine import fleet_kernel

        registry = default_registry(plugins=["hyba_mine.fleet_kernel"])
        kernel = registry.get(fleet_kernel.KERNEL_NAME, fleet_kernel.KERNEL_VERSION)
        self.assertEqual(kernel.routes(), frozenset({"igpu", "reference"}))
        for adapter in (ReferenceAdapter(), IGPUAdapter()):
            record = adapter.self_test(KernelRegistry([kernel]))
            self.assertTrue(record.passed, record.error)
        params, payload = fleet_kernel.genesis_lane()
        executed, hits, probe = fleet_kernel.decode_output(kernel.reference_output(params, payload))
        self.assertEqual(executed, params["count"])
        self.assertIn(GENESIS.nonce, [nonce for _, nonce in hits])
        self.assertIsNotNone(probe)
        chronus_root = Path(importlib.import_module("chronus.fleet").__file__).resolve().parent
        self.assertFalse(any("hyba_mine" in p.read_text(encoding="utf-8") for p in chronus_root.rglob("*.py")))

    def test_fleet_results_pass_the_same_integrity_checks(self):
        fleet = FakeFleet()
        dispatcher = FleetDispatcher(fleet, ROUTE, backend="auto", prefer="ours")
        unit = _unit()
        result = asyncio.run(dispatcher.run(unit))
        self.assertIsNone(check_result_integrity(unit, result))
        self.assertIn(GENESIS.nonce, [hit.nonce for hit in result.hits])
        self.assertEqual((result.node, result.executed_route), ("imac", "fleet:igpu"))
        self.assertEqual(result.detail["executed_backend"], "igpu")
        sent = fleet.units[0]
        self.assertEqual((sent.kernel, sent.route, sent.prefer), ("hyba_mine.nonce_window", "auto", "ours"))
        self.assertEqual(sent.payload, unit.header_prefix)
        self.assertNotIn("username", json.dumps(sent.to_wire()))
        named = FakeFleet()
        asyncio.run(FleetDispatcher(named, ROUTE, backend="reference", prefer="host").run(_unit()))
        self.assertEqual((named.units[0].route, named.units[0].prefer), ("reference", None))

    def test_unverified_or_mismatched_fleet_replies_are_refused(self):
        class Unverified:
            def submit(self, unit, timeout=None):
                return type("Reply", (), {"verified": False, "receipt": {}, "output": b""})()

        with self.assertRaises(DispatchError):
            asyncio.run(FleetDispatcher(Unverified(), ROUTE).run(_unit()))

        def other_unit(output, receipt):
            receipt["work_unit"]["digest"] = "f" * 64
            return output, receipt

        with self.assertRaises(DispatchError):
            asyncio.run(FleetDispatcher(FakeFleet(other_unit), ROUTE).run(_unit()))
        with self.assertRaises(DispatchError):
            asyncio.run(FleetDispatcher(FakeFleet(lambda o, r: (o[:-4], r)), ROUTE).run(_unit()))
        with self.assertRaises(DispatchError):
            FleetDispatcher(object(), ROUTE)

    def test_a_nonce_window_through_an_in_process_fleet(self):
        import os
        import tempfile

        from chronus.fleet.executor import FleetExecutor

        previous = os.environ.get("CHRONUS_FLEET_KERNELS")
        os.environ["CHRONUS_FLEET_KERNELS"] = "hyba_mine.fleet_kernel"
        tmp = tempfile.TemporaryDirectory(prefix="hyba-mine-fleet-", ignore_cleanup_errors=True)
        try:
            fleet = FleetExecutor.embedded(Path(tmp.name) / "state", local_workers=2,
                                           worker_routes=["igpu", "reference"], fabric_tick_ms=200)
            try:
                unit = _unit()
                result = asyncio.run(FleetDispatcher(fleet, ROUTE, backend="auto", prefer="ours").run(unit))
                self.assertIsNone(check_result_integrity(unit, result))
                self.assertIn(GENESIS.nonce, [hit.nonce for hit in result.hits])
                self.assertEqual(result.detail["executed_backend"], "igpu")
                self.assertEqual(result.detail["tier"], "Tier 1")
                named = asyncio.run(FleetDispatcher(fleet, ROUTE, backend="reference").run(unit))
                self.assertEqual(named.detail["executed_backend"], "reference")
                self.assertEqual(named.hits, result.hits)
                with self.assertRaises(DispatchError):
                    asyncio.run(FleetDispatcher(fleet, ROUTE, backend="metal").run(unit))
            finally:
                fleet.close()
        finally:
            if previous is None:
                os.environ.pop("CHRONUS_FLEET_KERNELS", None)
            else:
                os.environ["CHRONUS_FLEET_KERNELS"] = previous
            tmp.cleanup()


class TestLocalDispatch(unittest.TestCase):
    def test_local_dispatcher_and_absent_fleet_package(self):
        saved = sys.modules.get("chronus.fleet.executor")
        sys.modules["chronus.fleet.executor"] = None
        try:
            self.assertIsNone(load_fleet_executor())
        finally:
            if saved is None:
                sys.modules.pop("chronus.fleet.executor", None)
            else:
                sys.modules["chronus.fleet.executor"] = saved
        dispatcher = LocalIGPUDispatcher(ModeALane(workers=1), ROUTE)
        unit = _unit()
        result = asyncio.run(dispatcher.run(unit))
        self.assertIsNone(check_result_integrity(unit, result))
        self.assertEqual(dispatcher.describe()["lane"]["route"], ROUTE_MODE_A)
        self.assertEqual(dispatcher.describe()["route"]["executed_backend"], "igpu")
        dispatcher.close()


def _source_files():
    roots = [PACKAGE_ROOT, REPO_ROOT / "scripts" / "mine", REPO_ROOT / "docs" / "mine"]
    files = []
    for root in roots:
        if root.exists():
            files.extend(p for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    workflow = REPO_ROOT / ".github" / "workflows" / "hyba-mine-mac.yml"
    if workflow.exists():
        files.append(workflow)
    return files


class TestSeparationAndHygiene(unittest.TestCase):
    def test_chronus_never_imports_hyba_mine(self):
        chronus_root = Path(importlib.import_module("chronus").__file__).resolve().parent
        offenders = []
        for path in chronus_root.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r"^\s*(from|import)\s+hyba_mine\b", text, re.M):
                offenders.append(str(path))
        self.assertEqual(offenders, [])

    def test_catalogue_is_exactly_the_four_owner_pools(self):
        self.assertEqual(sorted(POOL_CATALOG), ["braiins", "ckpool", "nicehash", "viabtc"])
        for profile in POOL_CATALOG.values():
            self.assertNotIn("d=", profile.password_hint)

    def test_every_new_file_carries_the_hyba_copyright(self):
        missing = [str(p) for p in _source_files() if p.suffix in (".py", ".sh", ".md", ".toml", ".yml")
                   and COPYRIGHT not in p.read_text(encoding="utf-8")]
        self.assertEqual(missing, [])

    def test_no_claim_tokens_and_no_mode_a_mislabels(self):
        token_file = REPO_ROOT / "scripts" / "ci" / "claim_token_bytes.json"
        # Words are stored as code points so this file never contains them.
        if token_file.exists():
            tokens = [bytes(t).lower() for t in json.loads(token_file.read_text())]
        else:
            tokens = [bytes(word) for word in ((105, 110, 102, 105, 110, 105, 116, 101), (101, 120, 112, 111, 110, 101, 110, 116, 105, 97, 108), (117, 110, 108, 105, 109, 105, 116, 101, 100), (49, 48, 48, 120))]
        mislabels = [bytes(word) for word in ((99, 112, 117, 32, 102, 97, 108, 108, 98, 97, 99, 107), (110, 111, 32, 103, 112, 117), (106, 117, 115, 116, 32, 99, 112, 117))]
        problems = []
        for path in _source_files():
            data = path.read_bytes().lower()
            problems.extend((str(path), t.decode()) for t in tokens + mislabels if t in data)
        self.assertEqual(problems, [])

    def test_python_sources_parse_and_never_read_logins_from_the_environment(self):
        for path in (PACKAGE_ROOT / "src" / "hyba_mine").rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            ast.parse(text, filename=str(path))
            self.assertNotRegex(text, r"MINING_[A-Z]+_(USER|PASS)", str(path))
            self.assertNotIn("print(login", text)


if __name__ == "__main__":
    unittest.main()

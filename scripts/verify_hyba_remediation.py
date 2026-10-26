#!/usr/bin/env python3
"""Reproducible focused evidence. Never a deployment or live-yield certificate."""
from __future__ import annotations
import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = [
    'chronus/mla1517_platform/python/control_api.py',
    'chronus/mla1517_platform/python/runtime_config.py',
    'chronus/mla1517_platform/python/enterprise_api.py',
    'chronus/mla1517_platform/python/enterprise_contract.py',
    'aethel/enterprise/custody.py', 'aethel/enterprise/quarantine.py', 'lucas/ladder.py',
    'frontend/src/components/Header.tsx', 'frontend/src/components/ControlSession.tsx',
    'frontend/src/components/Header.test.tsx', 'frontend/src/lib/api.ts',
    'frontend/src/lib/status.ts', 'frontend/src/lib/__tests__/api.test.ts',
    'tests/test_hyba_enterprise_remediation.py', 'scripts/verify_hyba_remediation.py',
    '.github/workflows/hyba-evidence-contracts.yml', 'docs/operations/HYBA_BACKEND_REMEDIATION.md']

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--isolated-handler-imports',action='store_true',
        help='Explicit partial-checkout mode; not full-system CI')
    args=parser.parse_args()
    if args.isolated_handler_imports:
        os.environ['HYBA_ISOLATED_HANDLER_TEST']='1'
    else:
        os.environ.pop('HYBA_ISOLATED_HANDLER_TEST',None)
    day=datetime.now(timezone.utc).date().isoformat()
    folder=ROOT/'evidence'/day;folder.mkdir(parents=True,exist_ok=True)
    # Preserve genuine test output and return a failing exit code on any failure.
    stream=io.StringIO()
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_hyba_enterprise_remediation.py')
    with redirect_stdout(stream):
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (folder/'focused_tests.log').write_text(stream.getvalue())
    sys.path.insert(0,str(ROOT/'chronus/mla1517_platform/python'));sys.path.insert(0,str(ROOT))
    from enterprise_contract import ElevationCache, canonical, evidence_zip, measure_elevation, qualify_status
    cache=ElevationCache(measure_elevation)
    snapshots=[cache.get() for _ in range(3)]
    (folder/'chronus_elevation.json').write_bytes(canonical(snapshots[0]))
    source_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in SOURCES}
    (folder/'SOURCE_DIGESTS.json').write_text(json.dumps(source_hashes,sort_keys=True,indent=2)+'\n')
    checked_client=[name for name in SOURCES if name.startswith('frontend/') and '.test.' not in name]
    forbidden=('185.42','12.584321','843219','98.4','stratum+tcp://','stratum+ssl://')
    hits=[{'path':name,'needle':needle} for name in checked_client for needle in forbidden if needle in (ROOT/name).read_text()]
    report={
        'scope':'focused_local_contract_tests_not_deployment_or_live_mining',
        'baseline_commit':'75ece7ed9d66aad22c3e2564e85cb62b00fc8dfb',
        'generated_at':datetime.now(timezone.utc).isoformat(), 'python':platform.python_version(),
        'isolated_handler_imports':args.isolated_handler_imports,
        'isolated_boot_modules':['system_fabric','autonomous_supervisor','al_haras_pythia'] if args.isolated_handler_imports else [],
        'hardware_pool_treasury_in_http_tests':'explicit test doubles; no external operations',
        'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
        'focused_tests_pass':result.wasSuccessful(),
        'sequential_elevation_reads':3,'identical_digest':len({x['sha256'] for x in snapshots})==1,
        'elevation_sha256':snapshots[0]['sha256'], 'elevation_status':snapshots[0]['status'],
        'mining_certificate':qualify_status({})['ready_to_mine_certificate'],
        'source_grep':{'scope':checked_client,'hits':hits,'built_bundle':'NOT_RUN'},
        'api_studio_typescript_path':'NOT_APPLICABLE: separate repository',
        'legacy_chronos_package_path':'retained filesystem compatibility; not a public release claim',
        'full_checkout_ci':'NOT_RUN_LOCALLY','frontend_typecheck_build':'NOT_RUN',
        'deployed_proxy_curl':'NOT_RUN','live_hardware_and_pool':'NOT_RUN',
        'treasury_signer_and_observer':'UNAVAILABLE','customer_ledger_adapter':'UNAVAILABLE',
        'ovid_grf2_crt_database_suites':'NOT_RUN','quorum_reseal_ceremony':'NOT_RUN',
        'zero_alloc_and_independent_authority_suites':'NOT_RUN',
        'R1_R7_release_complete':False,
    }
    (folder/'validation.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    # These are actual HTTP handler test logs, deliberately identified as fixture
    # traffic. No deployed curl, secret-bearing cookie, or token is printed.
    http_lines=[line for line in stream.getvalue().splitlines() if '[pythia-control]' in line]
    (folder/'journey.log').write_text('LOCAL HTTP FIXTURE TESTS ONLY. See focused_tests.log and validation.json.\n'+'\n'.join(http_lines)+'\n')
    (folder/'REMEDIATION_STATUS.md').write_text(
        "# R1–R7 closure status\n\nPASS below means focused local contract evidence only; "
        "FAIL means the requested full release proof is not closed. All production promotion remains blocked.\n\n"
        "| Item | Status | Evidence / outstanding gate |\n| --- | --- | --- |\n"
        "| R1 | PASS (local) | Fail-closed status/readiness tests; no deployed or live-pool proof. |\n"
        "| R2 | PASS (local) | Three identical boot-cache digests, stale-on-error; Mode A CPU reference only. |\n"
        "| R3 | FAIL (release) | Sessions/roles/allowlists/dual approval/auto-disarm locally tested; full guardian/UI/deployment journey pending. |\n"
        "| R4 | FAIL (release) | Offline treasury and withdrawal refusal tested; observer/signer and bundle proof unavailable. |\n"
        "| R5 | FAIL (release) | Quarantine retention tested; CRT/GRF2/database and quorum recovery suites NOT_RUN. |\n"
        "| R6 | FAIL (release) | Exact invariant/rung/stride boundaries tested; zero-alloc and requested independent suite counts NOT_RUN. |\n"
        "| R7 | FAIL (release) | ZIP/digest and accounting contracts tested; canonical customer ledger unavailable. |\n\n"
        "Mining certificate: WITHHELD. AI Studio repository untouched.\n")
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()
           if p.is_file() and p.name in {'focused_tests.log','chronus_elevation.json','SOURCE_DIGESTS.json','validation.json','journey.log','REMEDIATION_STATUS.md'}}
    (folder/'DIGESTS.json').write_text(json.dumps({'schema_version':'hyba.evidence/1','files':files},sort_keys=True,indent=2)+'\n')
    data,zip_hash=evidence_zip(ROOT/'evidence',day)
    # Keep the binary out of the manifest/repository; it is derived from listed bytes.
    print(json.dumps({'tests_run':result.testsRun,'pass':result.wasSuccessful(),
        'isolated_handler_imports':args.isolated_handler_imports,'elevation_sha256':snapshots[0]['sha256'],
        'manifest_sha256':hashlib.sha256((folder/'DIGESTS.json').read_bytes()).hexdigest(),
        'export_zip_sha256':zip_hash,'export_zip_bytes':len(data),'certificate':'WITHHELD'},sort_keys=True))
    return 0 if result.wasSuccessful() and not hits and report['identical_digest'] and snapshots[0]['status']=='VERIFIED_SUBSTRATE_AGNOSTIC' else 1

if __name__=='__main__':raise SystemExit(main())

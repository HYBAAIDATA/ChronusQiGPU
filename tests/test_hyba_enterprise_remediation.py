"""Focused contracts; fixture hardware is not live mining evidence.

Run: python -m unittest discover -s tests -p test_hyba_enterprise_remediation.py -v
The optional HYBA_ISOLATED_HANDLER_TEST=1 mode stubs only unrelated boot-service
imports in a partial source checkout. Do not treat that mode as full-system CI.
"""
from __future__ import annotations
import copy
import hashlib
import hmac
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT / 'chronus/mla1517_platform/python'
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(PLATFORM))
from enterprise_contract import (COOKIE, ElevationCache, OperatorSecurity, Refusal,
    SealedAudit, canonical, economics, envelope, evidence_zip, measure_elevation,
    qualify_status, sha256)
from enterprise_api import EnterpriseService, CanonicalBackend
from lucas.ladder import FULL_LADDER, require_release_rung

# Synthetic credentials exist only inside temporary tests. Never deployment secrets.
TEST_NAMES = {'founder': 'founder_ceo', 'second': 'approver', 'reader': 'operator'}
def mapping():
    return {name: {'role': role, 'token_sha256': hashlib.sha256(('fixture-'+name).encode()).hexdigest()}
            for name, role in TEST_NAMES.items()}
def positive():
    return {'gpu': {'physical_gpu_available': True, 'detected_device': 'FIXTURE_ONLY'},
        'workers': {'fixture': {'liveness': True, 'readiness': True}},
        'runtime': {'live_submit': {'enabled': True}},
        'stratum': {'evidence_available': True, 'primary': {'transport':'CONNECTED', 'authorized':True},
                    'submission': {'last_result':'ACCEPTED','last_response_at':1000}, 'counters':{'accepted':1}},
        'execution_receipt': {'evidence_available':True,'worker_live':True,'emulated':False,
                              'execution_backend':'opencl:fixture','status':'PASS'},
        'ready_to_mine': {'ready':True,'details':{'hashrate_hs':12}}}

class StatusTests(unittest.TestCase):
    def test_offline_withheld(self):
        x=qualify_status({},now=1000)
        self.assertEqual(x['ready_to_mine_certificate'],'WITHHELD');self.assertFalse(x['ready_to_mine']['ready'])
        self.assertIn('Chronus',x['release_scope_label']);self.assertFalse(x['speedup_claimed'])
    def test_fixture_positive_predicate_only(self):
        self.assertEqual(qualify_status(positive(),now=1000)['ready_to_mine_certificate'],'ACTIVE')
    def test_every_gate_required(self):
        changes=[('gpu',{}),('workers',{}),('runtime',{}),('stratum',{}),('ready_to_mine',{}),('execution_receipt',{})]
        for key,value in changes:
            with self.subTest(key=key):
                x=positive();x[key]=value;self.assertEqual(qualify_status(x,now=1000)['ready_to_mine_certificate'],'WITHHELD')
    def test_ack_boundaries(self):
        for at in (700,699,1001,None,'1000',True,float('nan')):
            with self.subTest(at=at):
                x=positive();x['stratum']['submission']['last_response_at']=at
                self.assertFalse(qualify_status(x,now=1000)['ready_to_mine']['ready'])
    def test_rejected_ack(self):
        x=positive();x['stratum']['submission']['last_result']='REJECTED'
        self.assertFalse(qualify_status(x,now=1000)['ready_to_mine']['ready'])
    def test_accepted_counts(self):
        for n in (0,-1,True,1.0,'1',None):
            x=positive();x['stratum']['counters']['accepted']=n
            self.assertFalse(qualify_status(x,now=1000)['ready_to_mine']['ready'])
    def test_emulated_and_cpu_not_silicon(self):
        for changes in ({'emulated':True},{'execution_backend':'cpu'},{'status':'NOT_RUN'},{'status':None}):
            x=positive();x['execution_receipt'].update(changes)
            self.assertFalse(qualify_status(x,now=1000)['ready_to_mine']['ready'])
    def test_logical_gpu_not_physical(self):
        x=positive();x['gpu']={'physical_gpu_available':False,'logical_substrate':{'available':True}}
        self.assertFalse(qualify_status(x,now=1000)['ready_to_mine']['ready'])
    def test_does_not_mutate_observations(self):
        x=positive();before=copy.deepcopy(x);qualify_status(x,now=1000);self.assertEqual(x,before)
    def test_response_provenance(self):
        x=envelope({'quantum_result':{}},'/api/test',200)
        self.assertEqual(x['quantum_result']['device'],'not_observed');self.assertIsNone(x['hashrate'])
        self.assertFalse(x['speedup_claimed']);self.assertEqual(x['Route']['requested'],'/api/test')

class TempCase(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.env=patch.dict(os.environ,{'HYBA_AUTH_PRINCIPALS_JSON':json.dumps(mapping()),
            'HYBA_PUBLIC_ORIGIN':'https://operator.invalid','HYBA_AUDIT_HMAC_KEY':'ab'*32})
        self.env.start();self.audit=SealedAudit(self.root/'audit.sqlite3',b'k'*32);self.security=OperatorSecurity(self.audit)
    def tearDown(self):
        self.env.stop();self.tmp.cleanup()
    def login(self,name='founder',security=None):
        sec=security or self.security
        identity,token=sec.login({'principal_id':name,'credential':'fixture-'+name},'fixture')
        return {'Cookie':f'{COOKIE}={token}','Origin':'https://operator.invalid'},identity
    def refusal(self,call,reason):
        with self.assertRaises(Refusal) as ctx: call()
        self.assertEqual(ctx.exception.reason,reason)

class AuditTests(TempCase):
    def test_reopen_chain(self):
        a=self.audit.append('A');b=self.audit.append('B');rows=SealedAudit(self.audit.path,b'k'*32).records()
        self.assertEqual(rows[1]['previous_hash'],a);self.assertEqual(rows[1]['audit_hash'],b)
    def test_body_tamper(self):
        self.audit.append('A')
        with sqlite3.connect(self.audit.path) as db:db.execute("UPDATE audit SET body='{}'")
        self.refusal(self.audit.records,'AUDIT_INTEGRITY_FAILURE')
        self.refusal(lambda:self.audit.append('B'),'AUDIT_INTEGRITY_FAILURE')
    def test_wrong_key(self):
        self.audit.append('A');other=SealedAudit(self.audit.path,b'z'*32)
        self.refusal(other.records,'AUDIT_INTEGRITY_FAILURE')
    def test_concurrent_chain(self):
        with ThreadPoolExecutor(max_workers=6) as pool:list(pool.map(lambda i:self.audit.append('A',index=i),range(24)))
        self.assertEqual(len(self.audit.records()),24)
    def test_no_key(self):
        self.refusal(lambda:SealedAudit(self.root/'none',b''),'AUDIT_KEY_UNAVAILABLE')

class AuthTests(TempCase):
    def test_auth_and_role(self):
        headers,identity=self.login();self.assertEqual(identity['role'],'founder_ceo')
        self.assertEqual(self.security.principal(headers,{'founder_ceo'})[0],'founder')
        self.refusal(lambda:self.security.principal(headers,{'approver'}),'ROLE_REQUIRED')
    def test_bad_credentials(self):
        self.refusal(lambda:self.security.login({'principal_id':'founder','credential':'wrong'},'x'),'INVALID_CREDENTIAL')
    def test_missing_cookie(self):
        self.refusal(lambda:self.security.principal({}, {'founder_ceo'}),'SESSION_REQUIRED')
    def test_logout(self):
        headers,_=self.login();self.security.logout(headers)
        self.refusal(lambda:self.security.principal(headers,{'founder_ceo'}),'SESSION_EXPIRED')
    def test_expiry(self):
        headers,_=self.login()
        with patch('enterprise_contract.time.time',return_value=time.time()+3601):
            self.refusal(lambda:self.security.principal(headers,{'founder_ceo'}),'SESSION_EXPIRED')
    def test_secret_rotation_revokes_session(self):
        headers,_=self.login();m=mapping();m['founder']['token_sha256']='cd'*32
        with patch.dict(os.environ,{'HYBA_AUTH_PRINCIPALS_JSON':json.dumps(m)}):
            self.refusal(lambda:self.security.principal(headers,{'founder_ceo'}),'SESSION_REVOKED')
    def test_bad_secrets_fail_closed(self):
        for m in ('{}','[]','null','{"founder":4}','{"founder":{"role":"ceo","token_sha256":"bad"}}'):
            with patch.dict(os.environ,{'HYBA_AUTH_PRINCIPALS_JSON':m}):
                self.refusal(self.security.principals,'AUTH_SECRETS_NOT_CONFIGURED')
    def test_origin(self):
        self.security.origin({'Origin':'https://operator.invalid'})
        for origin in ('https://attacker.invalid','null',None):
            self.refusal(lambda:self.security.origin({'Origin':origin}),'ORIGIN_REQUIRED')
    def test_rate_limit(self):
        for _ in range(10):
            self.refusal(lambda:self.security.login({},'ratelimited'),'INVALID_CREDENTIAL')
        self.refusal(lambda:self.security.login({},'ratelimited'),'LOGIN_RATE_LIMITED')
    def test_approval_digest_and_replay(self):
        d=sha256({'request':1});a=self.security.approve('second','mining.start',d)
        self.refusal(lambda:self.security.consume(a['approval_id'],'founder','mining.start','00'*32),'SECOND_APPROVAL_REQUIRED')
        self.security.consume(a['approval_id'],'founder','mining.start',d)
        self.refusal(lambda:self.security.consume(a['approval_id'],'founder','mining.start',d),'SECOND_APPROVAL_REQUIRED')
    def test_self_approval_not_independent(self):
        a=self.security.approve('founder','mining.start','00'*32)
        self.refusal(lambda:self.security.consume(a['approval_id'],'founder','mining.start','00'*32),'SECOND_APPROVAL_REQUIRED')
    def test_approval_expiry(self):
        a=self.security.approve('second','treasury.withdraw','00'*32)
        with patch('enterprise_contract.time.time',return_value=time.time()+301):
            self.refusal(lambda:self.security.consume(a['approval_id'],'founder','treasury.withdraw','00'*32),'SECOND_APPROVAL_REQUIRED')
    def test_approval_action_bound(self):
        a=self.security.approve('second','mining.start','00'*32)
        self.refusal(lambda:self.security.consume(a['approval_id'],'founder','treasury.withdraw','00'*32),'SECOND_APPROVAL_REQUIRED')

class EvidenceTests(TempCase):
    def pack_folder(self,entries=None):
        self.day='2026-10-23';folder=self.root/self.day;folder.mkdir();(folder/'proof.log').write_bytes(b'actual bytes\n')
        files={'proof.log':hashlib.sha256((folder/'proof.log').read_bytes()).hexdigest()}
        (folder/'DIGESTS.json').write_text(json.dumps({'files': files if entries is None else entries}));return folder
    def test_pack_exact_hashes_and_determinism(self):
        self.pack_folder();data,digest=evidence_zip(self.root,self.day)
        self.assertEqual(hashlib.sha256(data).hexdigest(),digest);self.assertEqual(evidence_zip(self.root,self.day)[0],data)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            manifest=json.loads(archive.read(self.day+'/DIGESTS.json'))
            for name,expected in manifest['files'].items():self.assertEqual(hashlib.sha256(archive.read(self.day+'/'+name)).hexdigest(),expected)
    def test_tampered_pack_refused(self):
        folder=self.pack_folder();(folder/'proof.log').write_text('changed')
        self.refusal(lambda:evidence_zip(self.root,self.day),'EVIDENCE_DIGEST_MISMATCH')
    def test_path_traversal_refused(self):
        for name in ('../outside','/etc/passwd','a\\b','DIGESTS.json','.'):
            with self.subTest(name=name):
                folder=self.root/'2026-10-23';folder.mkdir(exist_ok=True);(folder/'DIGESTS.json').write_text(json.dumps({'files':{name:'00'*32}}))
                self.refusal(lambda:evidence_zip(self.root,'2026-10-23'),'EVIDENCE_PATH_REFUSED')
    def test_symlink_refused(self):
        folder=self.pack_folder();(folder/'proof.log').unlink();(folder/'proof.log').symlink_to(self.audit.path)
        self.refusal(lambda:evidence_zip(self.root,self.day),'EVIDENCE_PATH_REFUSED')
    def test_missing_manifest(self):
        (self.root/'2026-10-23').mkdir()
        self.refusal(lambda:evidence_zip(self.root,'2026-10-23'),'EVIDENCE_MANIFEST_INVALID')
    def test_missing_file(self):
        folder=self.pack_folder();(folder/'proof.log').unlink()
        self.refusal(lambda:evidence_zip(self.root,self.day),'EVIDENCE_NOT_AVAILABLE')
    def test_day_traversal(self):
        self.refusal(lambda:evidence_zip(self.root,'../2026-10-23'),'EVIDENCE_PATH_REFUSED')

class MathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.doc=measure_elevation()
    def test_measured_seeds(self):
        self.assertEqual([x['seed'] for x in self.doc['mode_a']['measurements']],[1337,42,2026])
        self.assertEqual(sum(x['bijection_points'] for x in self.doc['mode_a']['measurements']),3000)
        self.assertTrue(all(x['elapsed_ns']>0 for x in self.doc['mode_a']['measurements']))
    def test_no_mode_b_yield_claim(self):
        self.assertEqual(self.doc['mode_b']['status'],'OPENCL_UNAVAILABLE')
        self.assertFalse(self.doc['stride']['saves_hashes']);self.assertEqual(self.doc['postgres'],'DESIGN ONLY')
        self.assertEqual(self.doc['zero_alloc_tensor_manifest'],'NOT_RUN')
    def test_heuristics_honesty(self):
        self.assertTrue(all('not proof' in s for s in self.doc['heuristics'].values()))
    def test_elevation_three_identical_reads(self):
        cache=ElevationCache(lambda:self.doc);snapshots=[cache.get() for _ in range(3)]
        self.assertEqual(snapshots[0],snapshots[1]);self.assertEqual(snapshots[1],snapshots[2])
        self.assertEqual(snapshots[0]['sha256'],sha256(self.doc))
    def test_stale_on_error(self):
        cache=ElevationCache(lambda:self.doc);before=cache.get()
        self.assertFalse(cache.refresh(lambda:1/0));self.assertEqual(cache.get(),before)
    def test_initial_error_not_false_verified(self):
        cache=ElevationCache(lambda:1/0);self.assertEqual(cache.get()['status'],'UNVERIFIED')
    def test_release_rungs(self):
        for n in (10,12,15,18,20,31,50,76):self.assertEqual(require_release_rung(n),n)
        for n in (True,0,11,30,60,10.0):
            with self.assertRaises(ValueError):require_release_rung(n)
    def test_sha256_vectors(self):
        self.assertEqual(self.doc["sha256_vectors"]["nist_reference_points"],2)
        self.assertEqual(self.doc["sha256_vectors"]["genesis_80_byte"],"PASS")
    def test_gain_share(self):
        x=economics('100','60');self.assertEqual(x['fee'],'10.00');self.assertFalse(x['zero_fee_gate'])
    def test_zero_fee_gate(self):
        for folded in ('100','120'):self.assertTrue(economics('100',folded)['zero_fee_gate'])
    def test_invalid_economics(self):
        for value in ('NaN','Infinity','-1','bad'):
            with self.assertRaises(Refusal):economics(value,'0')

class FixtureBackend:
    """Test double; no real worker, wallet, pool, or hardware is instantiated."""
    def __init__(self):
        self.hardware=False;self.count=0;self.stops=0;self.starts=0
        self.cfg={'hashrate':{'ceiling_hs':100,'target_hs':0},'live_submit':{'enabled':False},'mining_policy':None}
    def status(self):
        x=qualify_status({});x['igpu_present']=self.hardware;return x
    def config(self):return copy.deepcopy(self.cfg)
    def pools(self):return [{'poolId':'fixture','label':'Fixture','region':'test','feeNote':'not live'}]
    def config_digest(self):return sha256(self.cfg)
    def configure(self,body,hardware):
        self.stop();self.cfg['mining_policy']={'poolId':body['poolId'],'shares_target':body['shares_target']}
        self.cfg['hashrate']['target_hs']=body['hashrate_hps'] if hardware else 0;return self.config_digest()
    def start(self):self.starts+=1;self.cfg['live_submit']['enabled']=True;return {'state':'START_REQUESTED'}
    def stop(self):self.stops+=1;self.cfg['live_submit']['enabled']=False;return {'state':'DISARMED'}
    def accepted(self):return self.count
    def treasury(self):return None
    def customers(self):return None
    def withdraw(self,body):raise Refusal(503,'HSM_TPM_SIGNER_UNAVAILABLE')

class ServiceTests(TempCase):
    def setUp(self):
        super().setUp();self.backend=FixtureBackend();self.service=EnterpriseService(self.backend,self.root/'state',self.root/'evidence',producer=lambda:{'mode_a':{'status':'PASS'},'status':'FIXTURE'})
        self.headers,_=self.login(security=self.service.security())
    def call(self,method,path,body=None,headers=None,guard=lambda *a:True):
        return self.service.dispatch(method,path,self.headers if headers is None else headers,body,guard=guard)
    def config_body(self):return {'poolId':'fixture','hashrate_hps':50,'shares_target':3}
    def test_public_status_withheld_redacted(self):
        r=self.call('GET','/api/mining/status',headers={});self.assertEqual(r.status,200)
        self.assertEqual(r.payload['ready_to_mine_certificate'],'WITHHELD');self.assertNotIn('runtime',r.payload)
    def test_public_pools_only_metadata(self):
        r=self.call('GET','/api/mining/pools',headers={})
        self.assertEqual(set(r.payload['pools'][0]),{'poolId','label','region','feeNote'})
    def test_protected_unauthorized(self):
        for p in ('/api/treasury/overview','/api/beta/customers','/api/evidence/pack','/api/auth/me'):
            self.assertEqual(self.call('GET',p,headers={}).status,401)
    def test_login_cookie_flags(self):
        r=self.call('POST','/api/auth/login',{'principal_id':'founder','credential':'fixture-founder'},headers={'Origin':'https://operator.invalid'})
        self.assertEqual(r.status,200)
        for flag in ('Secure','HttpOnly','SameSite=Strict','Path=/'):self.assertIn(flag,r.headers['Set-Cookie'])
    def test_approver_cannot_configure(self):
        headers,_=self.login('second',self.service.security())
        self.assertEqual(self.call('POST','/api/mining/configure',self.config_body(),headers).status,403)
    def test_offline_config_saved_disarmed(self):
        r=self.call('POST','/api/mining/configure',self.config_body())
        self.assertEqual(r.status,503);self.assertEqual(r.payload['error'],'NO_ATTACHED_MINING_HARDWARE')
        self.assertEqual(self.backend.cfg['hashrate']['target_hs'],0);self.assertFalse(self.backend.cfg['live_submit']['enabled'])
        self.assertEqual(len(r.payload['audit_hash']),64)
    def test_bad_pool(self):
        b=self.config_body();b['poolId']='attacker';self.assertEqual(self.call('POST','/api/mining/configure',b).status,400)
    def test_config_boundaries(self):
        for field,value in (('shares_target',0),('shares_target',10001),('shares_target',True),('hashrate_hps',101),('hashrate_hps',-1),('hashrate_hps',float('nan'))):
            b=self.config_body();b[field]=value;self.assertEqual(self.call('POST','/api/mining/configure',b).status,400)
    def test_guardian_absence_no_mutation(self):
        r=self.call('POST','/api/mining/configure',self.config_body(),guard=None)
        self.assertEqual(r.status,503);self.assertEqual(self.backend.stops,0)
    def test_guardian_denial_no_mutation(self):
        self.assertIsNone(self.call('POST','/api/mining/configure',self.config_body(),guard=lambda *a:False))
        self.assertEqual(self.backend.stops,0)
    def test_no_start_offline(self):
        self.call('POST','/api/mining/configure',self.config_body())
        r=self.call('POST','/api/mining/start',{});self.assertEqual(r.status,503);self.assertEqual(self.backend.starts,0)
    def test_independent_start_then_target_disarm_fixture(self):
        self.backend.hardware=True;self.call('POST','/api/mining/configure',self.config_body())
        self.assertEqual(self.call('POST','/api/mining/start',{}).status,403)
        a=self.service.security().approve('second','mining.start',self.backend.config_digest())
        r=self.call('POST','/api/mining/start',{'approval_id':a['approval_id']});self.assertEqual(r.status,202)
        self.backend.count=2;self.service.observe_target();self.assertTrue(self.backend.cfg['live_submit']['enabled'])
        self.backend.count=1;self.service.observe_target();self.assertFalse(self.backend.cfg['live_submit']['enabled'])
        self.assertEqual(self.service.security().audit.records()[-1]['event'],'MINING_AUTO_DISARM')
    def test_boot_revokes_persisted_intent(self):
        self.backend.cfg['mining_policy']={'shares_target':3};self.backend.cfg['live_submit']['enabled']=True
        self.service.boot();self.service.close();self.assertFalse(self.backend.cfg['live_submit']['enabled'])
    def test_boot_revokes_legacy_live_intent(self):
        self.backend.cfg["live_submit"]["enabled"]=True
        self.service.boot();self.service.close();self.assertFalse(self.backend.cfg["live_submit"]["enabled"])
    def test_treasury_offline_no_numbers(self):
        r=self.call('GET','/api/treasury/overview');self.assertEqual(r.payload['status'],'OFFLINE')
        self.assertIsNone(r.payload['balance']);self.assertIsNone(r.payload['price'])
    def test_withdraw_signer_missing(self):
        b={'amount':'1','destination':'fixture','network':'fixture'}
        a=self.service.security().approve('second','treasury.withdraw',sha256(b))
        r=self.call('POST','/api/treasury/withdraw',{**b,'approval_id':a['approval_id']})
        self.assertEqual(r.status,503);self.assertEqual(r.payload['error'],'HSM_TPM_SIGNER_UNAVAILABLE')
    def test_withdraw_no_client_signing(self):
        self.assertEqual(self.call('POST','/api/treasury/withdraw',{'private_key':'fixture'}).status,400)
    def test_nonobject_request(self):
        self.assertEqual(self.call('POST','/api/auth/login',[]).status,400)
    def test_csrf_origin(self):
        headers=dict(self.headers);headers['Origin']='https://attacker.invalid'
        self.assertEqual(self.call('POST','/api/mining/stop',{},headers).status,403)
    def test_elevation_read_200_identical(self):
        rows=[self.call('GET','/api/chronus/elevation',headers={}) for _ in range(3)]
        self.assertTrue(all(r.status==200 for r in rows));self.assertEqual(len({r.payload['sha256'] for r in rows}),1)

class QuarantineTests(TempCase):
    def test_retention_and_latch(self):
        spec=importlib.util.spec_from_file_location('quarantine_standalone',ROOT/'aethel/enterprise/quarantine.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        q=mod.CustodyQuarantine(self.root,b'k'*32);source=self.root/'bad';source.write_bytes(b'corrupt')
        incident=q.capture('../untrusted-record',{'primary':source})
        self.assertTrue(q.blocked('../untrusted-record'));self.assertEqual(source.read_bytes(),b'corrupt')
        mac=incident.pop('hmac_sha256');self.assertEqual(mac,hmac.new(b'k'*32,canonical(incident),hashlib.sha256).hexdigest())
        self.assertEqual(incident['severity'],'SEV-1')
        self.assertEqual(incident['release'],'MANUAL_QUORUM_RESEAL_REQUIRED')
        self.assertEqual(len(list((self.root/'quarantine').rglob('*.bin'))),1)

class HandlerTests(TempCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv('HYBA_ISOLATED_HANDLER_TEST') == '1':
            for name in ('system_fabric','autonomous_supervisor','al_haras_pythia'):
                sys.modules[name]=types.ModuleType(name)
            sys.modules['al_haras_pythia'].pythia_guardian_api=None
        import control_api
        cls.api=control_api
    def setUp(self):
        super().setUp();self.backend=FixtureBackend()
        self.service=EnterpriseService(self.backend,self.root/'state',self.root/'evidence',producer=lambda:{'status':'FIXTURE','mode_a':{'status':'PASS'}})
        self.patches=[patch.object(self.api,'_enterprise_service',return_value=self.service),
                      patch.object(self.api,'status_payload',side_effect=self.backend.status)]
        for p in self.patches:p.start()
        self.server=self.api.ThreadingHTTPServer(('127.0.0.1',0),self.api._Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        for p in reversed(self.patches):p.stop()
        super().tearDown()
    def request(self,path,method='GET',body=None,headers=None):
        conn=http.client.HTTPConnection(*self.server.server_address,timeout=5)
        conn.request(method,path,body=None if body is None else json.dumps(body),headers=headers or {})
        r=conn.getresponse();data=r.read();out=(r.status,dict(r.getheaders()),json.loads(data));conn.close();return out
    def test_status_and_readiness_agree(self):
        a=self.request('/api/mining/status');b=self.request('/ready-to-mine')
        self.assertEqual((a[0],b[0]),(200,503));self.assertEqual(a[2]['ready_to_mine_certificate'],b[2]['certificate'])
        self.assertIn('Route',a[2]);self.assertFalse(b[2]['ready'])
    def test_http_elevation_three_and_digest(self):
        rows=[self.request('/api/chronus/elevation') for _ in range(3)]
        self.assertTrue(all(r[0]==200 for r in rows));self.assertEqual(len({r[2]['sha256'] for r in rows}),1)
        self.assertEqual(self.request('/api/chronus/digest')[2]['sha256'],rows[0][2]['sha256'])
    def test_http_login_me_logout(self):
        status,headers,body=self.request('/api/auth/login','POST',{'principal_id':'founder','credential':'fixture-founder'},{'Origin':'https://operator.invalid','Content-Type':'application/json'})
        self.assertEqual(status,200);cookie=headers['Set-Cookie'].split(';')[0]
        self.assertEqual(self.request('/api/auth/me',headers={'Cookie':cookie})[2]['role'],'founder_ceo')
        principal,refusal=self.api.authenticate_control_principal({'Cookie':cookie})
        self.assertIsNone(refusal);self.assertEqual(principal.role,'ceo')
        self.assertEqual(self.request('/api/auth/logout','POST',{}, {'Cookie':cookie,'Origin':'https://operator.invalid'})[0],200)
        self.assertEqual(self.request('/api/auth/me',headers={'Cookie':cookie})[0],401)
    def test_http_unauthorized_401(self):
        self.assertEqual(self.request('/api/treasury/overview')[0],401)
    def test_http_pack_download_exact_hash(self):
        from datetime import datetime, timezone
        day=datetime.now(timezone.utc).date().isoformat()
        folder=self.service.evidence_root/day;folder.mkdir(parents=True)
        blob=b"fixture evidence, not live yield\n"
        (folder/'proof.log').write_bytes(blob)
        (folder/'DIGESTS.json').write_text(json.dumps({'files':{'proof.log':hashlib.sha256(blob).hexdigest()}}))
        headers,_=self.login(security=self.service.security())
        conn=http.client.HTTPConnection(*self.server.server_address,timeout=5)
        conn.request('GET','/api/evidence/pack',headers=headers)
        response=conn.getresponse();data=response.read()
        self.assertEqual(response.status,200)
        self.assertEqual(response.getheader('Content-Type'),'application/zip')
        self.assertEqual(response.getheader('X-Content-SHA256'),hashlib.sha256(data).hexdigest())
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertEqual(archive.read(day+'/proof.log'),blob)
        conn.close()
    def test_http_legacy_cookie_csrf_rejected(self):
        headers,_=self.login(security=self.service.security());headers.pop('Origin')
        self.assertEqual(self.request('/api/v1/config','PUT',{},headers)[0],403)
    def test_http_missing_audit_key_mutation_blocked(self):
        with patch.dict(os.environ,{'HYBA_AUDIT_HMAC_KEY':''}):
            self.assertEqual(self.request('/api/auth/login','POST',{}, {'Origin':'https://operator.invalid'})[0],503)
    def test_http_guardian_missing_503(self):
        headers,_=self.login(security=self.service.security())
        with patch.object(self.api,'pythia_guardian_api',None):
            r=self.request('/api/mining/configure','POST',{'poolId':'fixture','hashrate_hps':0,'shares_target':1},headers)
            self.assertEqual(r[0],503);self.assertEqual(self.backend.stops,0)
    def test_cookie_role_retained_for_guardian_read(self):
        headers,_=self.login(security=self.service.security())
        self.assertIsNone(self.api.console_read_authorization('/api/v1/mining/evidence',headers))
    def test_canonical_offline_config_durable(self):
        import runtime_config
        with patch.dict(os.environ,{'PYTHIA_RUNTIME_CONFIG':str(self.root/'runtime.json')}):
            control=types.SimpleNamespace(stop_workers=lambda:None)
            api=types.SimpleNamespace(runtime_config=runtime_config,_control_plane=lambda:control)
            backend=CanonicalBackend(api)
            pool=backend.pools()[0]['poolId']
            digest=backend.configure({'poolId':pool,'hashrate_hps':90,'shares_target':2},False)
            cfg=runtime_config.load()
            self.assertEqual(cfg['hashrate']['target_hs'],0)
            self.assertFalse(cfg['live_submit']['enabled'])
            self.assertEqual(cfg['mining_policy']['shares_target'],2)
            self.assertEqual(digest,backend.config_digest())
    def test_legacy_endpoint_smuggling_refused(self):
        import runtime_config
        with patch.dict(os.environ,{'PYTHIA_RUNTIME_CONFIG':str(self.root/'runtime.json')}):
            api=types.SimpleNamespace(runtime_config=runtime_config)
            backend=CanonicalBackend(api);cfg=runtime_config.load()
            cfg['mining_policy']={'poolId':backend.pools()[0]['poolId'],'shares_target':1}
            cfg['pools']=[{'endpoint':'stratum+tcp://attacker.invalid:3333','worker':'fixture','password':'fixture','enabled':True}]
            runtime_config.save(cfg)
            self.refusal(backend.start,'POOL_ENDPOINT_NOT_ALLOWLISTED')
    def test_legacy_direct_arm_rejected(self):
        with patch.object(self.api.runtime_config,'load',return_value=self.backend.config()):
            with self.assertRaisesRegex(ValueError,'DUAL_AUTHORITY_REQUIRED'):
                self.api._config_merge_sections({'live_submit':{'enabled':True}})
    def test_legacy_change_revokes_approval(self):
        self.backend.cfg['live_submit']['enabled']=True
        with patch.object(self.api.runtime_config,'load',return_value=self.backend.config()):
            cfg=self.api._config_merge_sections({'hashrate':{'target_hs':1}})
            self.assertFalse(cfg['live_submit']['enabled'])

if __name__=='__main__':unittest.main()

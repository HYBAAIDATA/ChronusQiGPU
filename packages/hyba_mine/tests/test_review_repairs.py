# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Regressions for recovery, private credentials and bounded network state."""
import asyncio
import json
import os
import plistlib
import subprocess
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, patch

from _support import TempHome
from hyba_mine import autostart
from hyba_mine.control import (block_pool, block_for, clear_block, clear_control_request,
                               read_control_request, request_pool_switch, update_state, load_state)
from hyba_mine.credentials import CredentialStoreError, KeychainStore, PoolLogin
from hyba_mine.ledger import Ledger
from hyba_mine.logsafe import SECRETS, register_login
from hyba_mine.pools import get_pool
from hyba_mine.stratum import (ConnectionLost, MAX_PUSH_BACKLOG, StratumConnection, literal)


class RecoveryTests(unittest.TestCase):
    def test_short_writes_and_torn_recovery_preserve_original_bytes(self):
        with TempHome() as home:
            ledger = Ledger(home.layout.ledger)
            ledger.append('first')
            with ledger.path.open('ab') as out:
                out.write(b'{"unfinished":')
            original = ledger.path.read_bytes()
            write = os.write
            with patch('hyba_mine.ledger.os.write', side_effect=lambda fd, data: write(fd, data[:7])):
                ledger.append('after')
            self.assertTrue(ledger.path.read_bytes().startswith(original))
            result = ledger.verify()
            self.assertTrue(result.ok, result.error)
            self.assertEqual((result.records, result.torn_lines), (3, 1))
            self.assertEqual([r['kind'] for r in ledger.records()], ['first', 'tail_recovery', 'after'])

    def test_complete_damage_before_torn_tail_is_rejected(self):
        with TempHome() as home:
            ledger = Ledger(home.layout.ledger)
            ledger.append('first')
            with ledger.path.open('ab') as out:
                out.write(b'bad\npartial')
            self.assertFalse(ledger.verify().ok)

    def test_final_fragment_reads_are_bounded(self):
        import io
        from hyba_mine.ledger import _final_fragment, _TAIL_CHUNK
        class BoundedReader(io.BytesIO):
            def read(self, size=-1):
                self.assertion(size)
                return super().read(size)
            @staticmethod
            def assertion(size):
                if not 0 <= size <= _TAIL_CHUNK:
                    raise AssertionError('unbounded ledger read')
        self.assertEqual(_final_fragment(BoundedReader(b'old\n'*100000+b'tail')),b'tail')
        self.assertEqual(_final_fragment(BoundedReader(b'no-newline')),b'no-newline')

    def test_complete_malformed_final_record_is_not_a_recoverable_tail(self):
        with TempHome() as home:
            ledger = Ledger(home.layout.ledger)
            ledger.append('first')
            with ledger.path.open('ab') as out:
                out.write(b'{"broken":\n')
            self.assertFalse(ledger.verify().ok)
            ledger.append('after')
            self.assertFalse(ledger.verify().ok)

    def test_blocks_survive_other_pool_updates_and_concurrent_settings(self):
        with TempHome() as home:
            block_pool(home.layout, 'viabtc', 'rejected')
            block_pool(home.layout, 'braiins', 'rejected')
            clear_block(home.layout, 'braiins')
            self.assertIsNotNone(block_for(home.layout, 'viabtc'))
            self.assertIsNone(block_for(home.layout, 'braiins'))
            with ThreadPoolExecutor(2) as pool:
                futures = [pool.submit(update_state, home.layout, **change) for change in
                           ({'active_pool': 'viabtc'}, {'tls_policy': 'require'})]
                for future in futures:
                    future.result()
            state = load_state(home.layout)
            self.assertEqual((state['active_pool'], state['tls_policy']), ('viabtc', 'require'))
            old = request_pool_switch(home.layout, 'viabtc')
            new = request_pool_switch(home.layout, 'braiins')
            clear_control_request(home.layout, old['request_id'])
            self.assertEqual(read_control_request(home.layout), new)


class CredentialTests(unittest.TestCase):
    def tearDown(self):
        SECRETS.clear()

    def test_short_hex_password_redacts_strings_without_changing_numeric_values(self):
        register_login('private.account.worker', 'ab')
        message = {'id': 123, 'result': [256, 'password ab', {'token': 'ab'}]}
        clean = literal(message)
        self.assertEqual(clean['id'], 123)
        self.assertEqual(clean['result'][0], 256)
        self.assertNotIn('ab', json.dumps(clean))
        self.assertEqual(message['result'][1], 'password ab')

    def test_one_character_password_preserves_pool_ids_and_hashes(self):
        register_login('private.account.worker', 'a')
        data = literal({'pool': 'viabtc', 'hash':'abc123', 'params':['password a'], 'password':'anything'})
        self.assertEqual(data['pool'],'viabtc')
        self.assertEqual(data['hash'],'abc123')
        self.assertEqual(data['params'],['password [redacted]'])
        self.assertEqual(data['password'],'[redacted]')

    def test_keychain_write_has_no_credentials_in_arguments_and_safe_timeout(self):
        store = KeychainStore(command=('/bin/true',))
        login = PoolLogin('private.account.worker', 'password-secret')
        calls = []
        def run(argv, **kwargs):
            calls.append((argv, kwargs))
            raise subprocess.TimeoutExpired(argv, 30, output='password-secret')
        with patch('hyba_mine.credentials.subprocess.run', side_effect=run):
            with self.assertRaises(CredentialStoreError) as caught:
                store.put('viabtc', login)
        self.assertEqual(calls[0][0], ['/bin/true', '-i'])
        self.assertIn(login.password.encode().hex(), calls[0][1]['input'])
        self.assertNotIn(login.password, str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)

    def test_autostart_no_start_preserves_custom_venv_and_does_not_bootstrap(self):
        with TempHome() as home:
            script = home.root / 'run.sh'
            script.write_text('exit 0\n')
            dest = home.root / 'agent.plist'
            with patch.object(autostart, 'is_macos', return_value=True), \
                    patch.object(autostart, 'launch_agent_path', return_value=dest), \
                    patch.object(autostart, '_launchctl') as launch, \
                    patch.dict(os.environ, {'HYBA_MINE_VENV': '/custom/venv'}):
                autostart.enable(script, home.layout, start=False)
            launch.assert_not_called()
            self.assertEqual(plistlib.loads(dest.read_bytes())['EnvironmentVariables']['HYBA_MINE_VENV'], '/custom/venv')


class NetworkBoundsTests(unittest.IsolatedAsyncioTestCase):
    async def test_rpc_timeout_and_expiry_release_pending_state(self):
        connection = StratumConnection(get_pool('viabtc').ordered_endpoints('off')[0])
        connection._send = AsyncMock()
        with self.assertRaises(asyncio.TimeoutError):
            await connection.call('unanswered', [], timeout=0.001)
        self.assertEqual(connection._pending, {})
        self.assertEqual(connection._expiry_handles, {})
        request_id, future = await connection.request('unanswered', [])
        connection._expiry_handles[request_id].cancel()
        connection._expire_request(request_id)
        with self.assertRaises(asyncio.TimeoutError):
            await future
        self.assertEqual(connection._pending, {})

    async def test_push_backlog_fails_closed(self):
        connection = StratumConnection(get_pool('viabtc').ordered_endpoints('off')[0])
        for _ in range(MAX_PUSH_BACKLOG):
            await connection._server_method({'method': 'client.show_message', 'params': []})
        with self.assertRaises(ConnectionLost):
            await connection._server_method({'method': 'client.show_message', 'params': []})
        connection._mark_closed('backlog')
        self.assertTrue(connection.closed.is_set())
        self.assertEqual(connection.pushes.qsize(), MAX_PUSH_BACKLOG)

    def test_tls_prefer_does_not_include_plaintext_when_tls_is_published(self):
        for pool_id in ('viabtc', 'nicehash'):
            endpoints = get_pool(pool_id).ordered_endpoints('prefer')
            self.assertTrue(endpoints)
            self.assertTrue(all(e.tls for e in endpoints))


class FollowupRepairTests(unittest.TestCase):
    def tearDown(self):
        SECRETS.clear()

    def test_recovery_resumes_after_two_interrupted_writes_and_detects_tampering(self):
        with TempHome() as home:
            ledger=Ledger(home.layout.ledger);ledger.append('first')
            with ledger.path.open('ab') as out:out.write(b'garbage')
            before=ledger.path.read_bytes();write=os.write
            def interrupted():
                calls=0
                def partial(fd,data):
                    nonlocal calls
                    calls+=1
                    if calls>1:raise OSError('interrupted recovery')
                    return write(fd,data[:7])
                return partial
            for _ in range(2):
                with patch('hyba_mine.ledger.os.write',side_effect=interrupted()):
                    with self.assertRaises(OSError):ledger.append('recovering')
            ledger.append('finished')
            self.assertTrue(ledger.path.read_bytes().startswith(before))
            self.assertTrue(ledger.verify().ok,ledger.verify().error)
            self.assertEqual([r['kind'] for r in ledger.records()],['first','tail_recovery','recovering','finished'])
            # A different pending recovery cannot overwrite a modified prefix.
            with ledger.path.open('ab') as out:out.write(b'partial')
            with patch('hyba_mine.ledger.os.write',side_effect=interrupted()):
                with self.assertRaises(OSError):ledger.append('another')
            data=bytearray(ledger.path.read_bytes());data[10]^=1;ledger.path.write_bytes(data)
            with self.assertRaisesRegex(ValueError,'prefix'):ledger.append('refused')
            self.assertFalse(ledger.verify().ok)

    def test_concurrent_credential_updates_keep_all_pool_logins(self):
        import threading
        import time
        from hyba_mine.credentials import FileStore
        with TempHome() as home:
            store=FileStore(home.layout.credentials);original=store._load
            def slow_load():
                data=original();time.sleep(0.01);return data
            barrier=threading.Barrier(4)
            def put(pool):
                barrier.wait();store.put(pool,PoolLogin(f'account.{pool}','synthetic'))
            with patch.object(store,'_load',side_effect=slow_load):
                with ThreadPoolExecutor(4) as executor:list(executor.map(put,['viabtc','braiins','ckpool','nicehash']))
            self.assertEqual(len(store._load()),4)

    def test_blocked_cli_switch_preserves_saved_healthy_pool(self):
        from argparse import Namespace
        from hyba_mine.cli import cmd_pool, EXIT_CONFIG
        with TempHome() as home:
            home.put_login('viabtc');update_state(home.layout,active_pool='braiins')
            block_pool(home.layout,'viabtc','rejected')
            with patch('hyba_mine.cli._miner_pid',return_value=123):
                self.assertEqual(cmd_pool(Namespace(action='use',pool='viabtc',wait=0)),EXIT_CONFIG)
            self.assertEqual(load_state(home.layout)['active_pool'],'braiins')

    def test_running_switch_waits_for_ack_before_persisting_default(self):
        from argparse import Namespace
        from hyba_mine.cli import cmd_pool
        with TempHome() as home:
            home.put_login('viabtc');update_state(home.layout,active_pool='braiins')
            with patch('hyba_mine.cli._miner_pid',return_value=123):
                cmd_pool(Namespace(action='use',pool='viabtc',wait=0))
            self.assertEqual(load_state(home.layout)['active_pool'],'braiins')
            self.assertEqual(read_control_request(home.layout)['pool_id'],'viabtc')

    def test_short_username_and_sensitive_json_keys_are_redacted_without_collisions(self):
        from hyba_mine.logsafe import redact_payload
        register_login('a.b','very-secret-password')
        clean=redact_payload({'very-secret-password':1,'a.b':2,'_redacted_key_0':3,'nested':{'a.b':'echo a.b'}})
        self.assertNotIn('a.b',json.dumps(clean));self.assertNotIn('very-secret-password',json.dumps(clean))
        self.assertEqual(len(clean),4)
        self.assertEqual(sorted(v for v in clean.values() if isinstance(v,int)),[1,2,3])


class LateResponseTests(unittest.IsolatedAsyncioTestCase):
    async def test_reply_after_ack_deadline_is_recorded_from_socket(self):
        from _support import VerifyingPool, GENESIS_EN2, GENESIS_NONCE
        from test_stratum import _session, _connected
        from test_runtime import Harness
        with TempHome() as home:
            home.put_login('viabtc')
            pool=VerifyingPool(reply_to_submits=False);await pool.start()
            session=_session(pool,[]);task=asyncio.create_task(session.run())
            h=Harness(home,{'viabtc':pool},submit_timeout=0.01)
            try:
                job=await _connected(session)
                submission=await session.submit(job,GENESIS_EN2,GENESIS_NONCE,reply_expiry=0.5)
                await h.runtime._await_reply('late-test',submission)
                self.assertFalse(submission.future.done())
                params=[session.login.username,job.job_id,GENESIS_EN2.hex(),job.job.ntime,f'{GENESIS_NONCE:08x}']
                accepted,_=pool.verify(params);self.assertTrue(accepted)
                for writer in pool.writers:
                    writer.write((json.dumps({'id':submission.request_id,'result':accepted,'error':None})+'\n').encode())
                    await writer.drain()
                await asyncio.wait_for(asyncio.shield(submission.future),0.5)
                await asyncio.sleep(0)
                replies=[r['data'] for r in h.ledger.records() if r['kind']=='pool_response']
                self.assertEqual(len(replies),1);self.assertTrue(replies[0]['late']);self.assertTrue(replies[0]['accepted'])
            finally:
                session.stop();await session.disconnect();await asyncio.wait_for(task,1);await pool.stop();h.runtime.dispatcher.close()

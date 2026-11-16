import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ExecutionAuthorityClient } from '../lib/execution-authority.ts';

// Synthetic transport contract only. Python integration tests exercise actual execution.
test('Python-compatible byte digest and authenticated synchronous request', async () => {
  const original = globalThis.fetch;
  const payload = Uint8Array.of(0, 255, 128, 42);
  const hash = Buffer.from(await crypto.subtle.digest('SHA-256', payload)).toString('hex');
  let request;
  globalThis.fetch = async (url, init) => {
    request = { url, init };
    return Response.json({ producer: 'CHRONUS', schema_version: 1, tenant_id: 'alice',
      run_id: 'test', status: 'COMPLETED', input_sha256: hash,
      receipt_object_id: 'a'.repeat(64), backend: 'python-math-reference' });
  };
  try {
    const client = new ExecutionAuthorityClient('http://localhost:8000', 'token', 'alice');
    const result = await client.execute(payload, 'scaling.v1');
    assert.equal(result.input_sha256, hash);
    assert.equal(request.init.headers.Authorization, 'Bearer token');
    assert.deepEqual(Buffer.from(JSON.parse(request.init.body).workload.payload_bytes.slice(7), 'base64'), Buffer.from(payload));
    assert.equal(request.url, 'http://localhost:8000/api/v1/execute');
    globalThis.fetch = async () => Response.json({ ...result, input_sha256: '0'.repeat(64) });
    await assert.rejects(client.execute(payload, 'scaling.v1'), /digest mismatch/);
    globalThis.fetch = async () => Response.json({ ...result, tenant_id: 'bob' });
    await assert.rejects(client.execute(payload, 'scaling.v1'), /invalid execution receipt/);
    globalThis.fetch = async () => new Response('', { status: 429 });
    await assert.rejects(client.execute(payload, 'scaling.v1'), /429/);
  } finally { globalThis.fetch = original; }
});

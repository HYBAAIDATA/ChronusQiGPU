import assert from 'node:assert/strict';
import { after, before, test } from 'node:test';
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import { performance } from 'node:perf_hooks';

const port = 31_000 + Math.floor(Math.random() * 5_000);
const baseUrl = `http://127.0.0.1:${port}`;
let server;

before(async () => {
  server = spawn('pnpm', ['exec', 'next', 'start', '--hostname', '127.0.0.1', '--port', String(port)], {
    cwd: process.cwd(),
    env: { ...process.env, NEXT_TELEMETRY_DISABLED: '1' },
    stdio: 'ignore',
  });

  for (let attempt = 0; attempt < 120; attempt += 1) {
    if (server.exitCode !== null) throw new Error(`Next server exited with code ${server.exitCode}`);
    try {
      const response = await fetch(`${baseUrl}/ciaas/welcome`);
      if (response.ok) return;
    } catch {
      // The server is still starting; poll again.
    }
    await delay(250);
  }
  throw new Error('Next server did not become ready within 30 seconds');
});

after(async () => {
  if (!server || server.exitCode !== null) return;
  server.kill('SIGTERM');
  await Promise.race([
    new Promise((resolve) => server.once('exit', resolve)),
    delay(2_000),
  ]);
  if (server.exitCode === null) server.kill('SIGKILL');
});

async function getHtml(path) {
  const response = await fetch(`${baseUrl}${path}`);
  assert.equal(response.status, 200, `${path} should return HTTP 200`);
  // React may insert comment delimiters between adjacent text nodes.
  // Exclude hydration scripts so assertions only inspect rendered markup.
  return (await response.text()).replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '').replace(/<!--.*?-->/gs, '');
}

test('welcome screen exposes the three metrics with inline provenance and an account action', async () => {
  const html = await getHtml('/ciaas/welcome');
  assert.match(html, /Welcome back\./);
  assert.match(html, /Avoided capex this period/);
  assert.match(html, /Speedup delivered/);
  assert.match(html, /Next invoice estimate/);
  assert.match(html, /Source: tenant settlement ledger\. Window: current billing period\. Last verified: not available\./);
  assert.match(html, /Source: verified benchmark artifact\. Window: current billing period\. Last verified: not available\./);
  assert.match(html, /Source: tenant settlement engine\. Window: current period to date\. Last verified: not available\./);
  assert.match(html, /href="\/ciaas\/account"[^>]*>.*View account/s);
  assert.match(html, /Sign-in is not available in this deployment\. Contact the platform operator\./);
  assert.doesNotMatch(html, /<dialog[\s>]|aria-modal="true"/i);
  assert.doesNotMatch(html, /<input\b[^>]*type="(?:password|email)"/i);
});

test('account overview refuses unsupported values and makes missing actions visible', async () => {
  const html = await getHtml('/ciaas/account');
  assert.match(html, /What is your account doing right now\?/);
  assert.match(html, /Account data unavailable/);
  assert.match(html, /Settlement and benchmark data are not available in this deployment\. Contact the platform operator\./);
  assert.match(html, /Live account feeds are not available in this deployment\. Contact the platform operator\./);
  assert.match(html, /href="\/ciaas\/provision"/);
  for (const label of ['Tier', 'Provisioned capacity and utilization', 'Avoided capex to date', 'Next invoice']) {
    assert.ok(html.includes(label), `missing account field: ${label}`);
  }
  assert.match(html, /Counterfactual spend − actual spend − incremental spend = avoided capex/);
  assert.match(html, /Source: tenant settlement engine\. Window: current billing period to date\. Last verified: not available\./);
  assert.match(html, /Capacity health/);
  assert.match(html, /Unverified/);
  assert.match(html, /Settlement history — unavailable/);
  assert.match(html, /Export data — unavailable/);
  assert.match(html, /Contact support — unavailable/);
  assert.match(html, /href="\/"[^>]*>.*Investigate service status/s);
});

test('welcome response completes within 1.2 seconds after warmup', async () => {
  await getHtml('/ciaas/welcome');
  const startedAt = performance.now();
  const response = await fetch(`${baseUrl}/ciaas/welcome`);
  const elapsedMs = performance.now() - startedAt;
  assert.equal(response.status, 200);
  assert.ok(elapsedMs < 1_200, `warm route took ${elapsedMs.toFixed(0)}ms`);
});

test('provisioning states unavailable sources and does not promise a working action', async () => {
  const html = await getHtml('/ciaas/provision');
  assert.match(html, /What do you need\?/);
  assert.match(html, /Provisioning is not available in this deployment\. Contact the platform operator\./);
  assert.match(html, /No capacity will be created/);
  assert.match(html, /Customer usage and approved default sizes are unavailable/);
  for (const option of ['Small', 'Medium', 'Large', 'Custom']) {
    assert.match(html, new RegExp(`>${option}</h3>`));
  }
  assert.match(html, /Projected cost — unavailable/);
  assert.match(html, /Source: tenant settlement projection\. Window: not available\. Last verified: not available\./);
  assert.match(html, /settlement window and charge date are not connected/);
  assert.match(html, /Projected avoided capex — unavailable/);
  assert.match(html, /Source: customer benchmark artifact\. Window: not available\. Last verified: not available\./);
  assert.match(html, /<button\b[^>]*disabled[^>]*>Provision — unavailable<\/button>/);
  assert.doesNotMatch(html, /Your capacity is live/);
  assert.doesNotMatch(html, /<input\b/i);
});

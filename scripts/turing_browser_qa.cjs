/* Optional local UI qualification: mocked HTTP transport, NEVER native/auth/billing evidence.
 * Requires playwright + @axe-core/playwright in an isolated test environment.
 * Serve the compiled TURING app with SPA fallback; set TURING_PREVIEW_URL.
 */
const { chromium } = require("playwright");
const { default: AxeBuilder } = require("@axe-core/playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const base = process.env.TURING_PREVIEW_URL || "http://127.0.0.1:8766";
const out = process.env.TURING_QA_OUTPUT || "/tmp/turing-browser-qa";
const pages = [
  "product",
  "capabilities",
  "how-it-works",
  "enterprise",
  "documentation",
  "security",
  "research",
  "contact",
  "legal/privacy",
  "legal/terms",
];
(async () => {
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({
    executablePath:
      process.env.CHROMIUM_PATH ||
      require("node:child_process")
        .execSync("command -v chromium")
        .toString()
        .trim(),
    headless: true,
    args: ["--no-sandbox"],
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
  });
  const page = await context.newPage();
  const errors = [],
    scans = [],
    network = [],
    keys = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  const envelope = {
    schema_version: "turing.workspace.v1",
    persistence: "in_memory_process_local",
    service_mode: "technical_evaluation_only",
  };
  const program = {
    n_qubits: 2,
    operations: [
      { gate: "h", qubits: [0] },
      { gate: "cx", qubits: [0, 1] },
    ],
  };
  const report = {
    fixture: "BROWSER QA ONLY — not native engine evidence",
    artifact_hash: "a".repeat(64),
    implementation_hash: "b".repeat(64),
    pipeline_report: {
      verdict: "PASS",
      program_digest: "c".repeat(64),
      certificate: { fixture: true },
      stages: [
        {
          stage: "request_validation",
          state: "PASS",
          detail: "Explicit UI-test fixture only.",
        },
        {
          stage: "custody",
          state: "SKIPPED",
          detail: "Not requested; no enterprise durability acceptance.",
        },
      ],
      result: {
        truth_class: "exact",
        backend: "exact_algebraic",
        payload: { fixture: true },
      },
    },
  };
  let state = "queued",
    attempts = 0,
    cancellationRequests = 0;
  await page.route("**/api/**", async (route) => {
    const req = route.request(),
      body = req.postDataJSON();
    network.push(req.url());
    if (body.action === "capabilities")
      return route.fulfill({
        json: {
          ...envelope,
          max_qubits: 12,
          max_operations: 256,
          max_amplitudes: 4096,
          gates: ["h", "cx"],
        },
      });
    if (body.action === "submit") {
      keys.push(body.idempotency_key);
      attempts++;
      if (attempts === 1) return route.abort("failed");
      if (attempts === 2)
        return route.fulfill({
          status: 403,
          json: { error: "fixture_subscription_expired" },
        });
    }
    if (body.action === "list") {
      let rows = Array.from({ length: 13 }, (_, i) => ({
        job_id: `fixture-job-${12 - i}`,
        status: i % 2 ? "failed" : "succeeded",
        submitted_at: `2026-10-19T15:00:${String(12 - i).padStart(2, "0")}Z`,
        n_qubits: 2,
        operation_count: 2,
      }));
      rows = rows.filter(
        (r) =>
          (!body.status || r.status === body.status) &&
          r.job_id.includes(body.query || ""),
      );
      const offset = body.offset || 0,
        limit = body.limit || 10;
      return route.fulfill({
        json: {
          ...envelope,
          jobs: rows.slice(offset, offset + limit),
          offset,
          limit,
          total_matching: rows.length,
          total_retained: 13,
          next_offset: offset + limit < rows.length ? offset + limit : null,
          observed_at: "2026-10-19T15:01:00Z",
        },
      });
    }
    let accepted;
    if (body.action === "cancel") {
      cancellationRequests++;
      accepted = state === "queued";
      if (accepted) state = "cancelled";
    }
    const job = {
      ...envelope,
      job_id: body.job_id || "fixture-job-local-ui-only",
      status: state,
      submitted_at: "2026-10-19T15:00:00Z",
      program,
    };
    if (body.action === "cancel") job.cancellation_accepted = accepted;
    if (state === "succeeded") job.report = report;
    return route.fulfill({ json: job });
  });
  async function audit(name) {
    assert.equal(
      await page.locator("h1").count(),
      1,
      `${name}: one page heading`,
    );
    assert.equal(
      await page.locator("main").count(),
      1,
      `${name}: one main landmark`,
    );
    assert.equal(
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      ),
      false,
      `${name}: no horizontal page overflow`,
    );
    const result = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
      .analyze();
    scans.push({
      name,
      violations: result.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        nodes: v.nodes.map((n) => n.target),
      })),
    });
    assert.deepEqual(result.violations, [], `${name}: automated WCAG checks`);
  }
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const p of pages) {
      await page.goto(`${base}/turing/${p}`);
      await page.locator("h1").waitFor();
      await audit(`${p}-${width}`);
      await page.screenshot({
        path: path.join(out, `${p.replaceAll("/", "-")}-${width}.png`),
        fullPage: true,
      });
      const targets = await page
        .locator('a[href^="/turing"]')
        .evaluateAll((a) => a.map((x) => x.getAttribute("href")));
      for (const href of targets)
        assert.ok(
          href === "/turing/app" ||
            href === "/turing" ||
            pages.some((p) => href === `/turing/${p}`),
          `No dead route: ${href}`,
        );
    }
  }
  await page.goto(`${base}/turing/contact`);
  await page
    .getByLabel("Computational task", { exact: true })
    .fill("Public-data circuit evaluation");
  await page
    .getByLabel("What would make the evaluation successful?")
    .fill("Inspect returned validation without inventing a numerical result.");
  const enquiryDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download evaluation brief" }).click();
  const enquiry = await enquiryDownload;
  const enquiryJson = JSON.parse(fs.readFileSync(await enquiry.path(), "utf8"));
  assert.equal(enquiryJson.delivery, "local_export_only_not_sent");
  await page
    .getByRole("status")
    .filter({ hasText: "It has not been sent" })
    .waitFor();
  await page.screenshot({
    path: path.join(out, "enquiry-export-390.png"),
    fullPage: true,
  });
  await page.goto(`${base}/turing/app`);
  await page.screenshot({
    path: path.join(out, "workspace-offline-390.png"),
    fullPage: true,
  });
  await audit("workspace-offline-390");
  await page.setViewportSize({ width: 1440, height: 1000 });
  async function connect(tenant = "fixture-tenant") {
    await page.getByLabel("Tenant identifier").fill(tenant);
    await page.getByLabel("Actor identifier").fill("fixture-actor");
    await page.getByLabel("Subscription bearer").fill("fixture-not-a-secret");
    await page
      .getByRole("button", {
        name: "Connect to evaluation service",
        exact: true,
      })
      .click();
  }
  await connect();
  await page
    .getByLabel("Native program · JSON")
    .fill('{"n_qubits":true,"operations":[]}');
  await page
    .getByRole("button", { name: "Review execution request", exact: true })
    .click();
  await page.getByRole("alert").waitFor();
  assert.equal(attempts, 0);
  await page
    .getByLabel("Native program · JSON")
    .fill(JSON.stringify(program, null, 2));
  await page
    .getByRole("button", { name: "Review execution request", exact: true })
    .click();
  await page
    .getByRole("heading", { name: "Review before execution" })
    .waitFor();
  await page.screenshot({
    path: path.join(out, "workspace-review-1440.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Confirm and submit", exact: true })
    .click();
  await page
    .getByRole("alert")
    .filter({ hasText: "Outcome unknown" })
    .waitFor();
  await page
    .getByRole("button", { name: "Retry the same request", exact: true })
    .click();
  await page.getByLabel("Subscription bearer").waitFor();
  await connect("wrong-tenant");
  await page
    .getByRole("alert")
    .filter({ hasText: "same tenant and actor" })
    .waitFor();
  assert.equal(keys.length, 2);
  await connect();
  await page
    .getByRole("button", { name: "Retry the same request", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Refresh job status", exact: true })
    .waitFor();
  assert.equal(keys.length, 3);
  assert.ok(keys.every((k) => k === keys[0]));
  await page
    .getByRole("button", { name: "Request cancellation", exact: true })
    .click();
  assert.equal(cancellationRequests, 0);
  await page
    .getByRole("button", { name: "Keep execution", exact: true })
    .click();
  assert.equal(cancellationRequests, 0);
  await page
    .getByRole("button", { name: "Request cancellation", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm cancellation request", exact: true })
    .click();
  await page
    .getByRole("status")
    .filter({ hasText: "Cancellation accepted" })
    .waitFor();
  assert.equal(cancellationRequests, 1);
  state = "running";
  await page
    .getByRole("button", { name: "Refresh job status", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Request cancellation", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm cancellation request", exact: true })
    .click();
  await page
    .getByRole("status")
    .filter({ hasText: "Cancellation not accepted" })
    .waitFor();
  state = "succeeded";
  await page
    .getByRole("button", { name: "Refresh job status", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Download returned report", exact: true })
    .waitFor();
  const resultDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download returned report" }).click();
  const downloaded = await resultDownload;
  assert.deepEqual(
    JSON.parse(fs.readFileSync(await downloaded.path(), "utf8")),
    report,
  );
  await page
    .getByRole("button", { name: "Refresh history", exact: true })
    .click();
  await page.locator(".t-history-list li").first().waitFor();
  assert.equal(await page.locator(".t-history-list li").count(), 10);
  await page.getByRole("button", { name: "Next page", exact: true }).click();
  await page.waitForFunction(
    () => document.querySelectorAll(".t-history-list li").length === 3,
  );
  await page
    .getByRole("button", { name: "Previous page", exact: true })
    .click();
  await page.waitForFunction(
    () => document.querySelectorAll(".t-history-list li").length === 10,
  );
  await page.getByLabel("Job state", { exact: true }).selectOption("failed");
  await page
    .getByRole("button", { name: "Refresh history", exact: true })
    .click();
  await page.waitForFunction(
    () => document.querySelectorAll(".t-history-list li").length === 6,
  );
  await page
    .getByLabel("Find a job identifier", { exact: true })
    .fill("fixture-job-11");
  await page
    .getByRole("button", { name: "Refresh history", exact: true })
    .click();
  await page.waitForFunction(
    () => document.querySelectorAll(".t-history-list li").length === 1,
  );
  await page
    .getByRole("button", { name: "Inspect job fixture-job-11", exact: true })
    .click();
  await page
    .locator(".t-job-details code")
    .filter({ hasText: "fixture-job-11" })
    .waitFor();
  // Independent state fixtures exercise UI branches, not legal native transitions.
  // Inspect a succeeded history row for evidence captures; do not pair a failed row with a success report.
  await page.getByLabel("Job state", { exact: true }).selectOption("succeeded");
  await page
    .getByLabel("Find a job identifier", { exact: true })
    .fill("fixture-job-12");
  await page
    .getByRole("button", { name: "Refresh history", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Inspect job fixture-job-12", exact: true })
    .click();
  await page
    .locator(".t-job-details code")
    .filter({ hasText: "fixture-job-12" })
    .waitFor();
  await audit("workspace-evidence-history-1440");
  await page.screenshot({
    path: path.join(out, "workspace-evidence-history-1440.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 1000 });
  await audit("workspace-evidence-history-390");
  await page.screenshot({
    path: path.join(out, "workspace-evidence-history-390.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", {
      name: "Disconnect and clear this view",
      exact: true,
    })
    .click();
  assert.equal(await page.getByLabel("Subscription bearer").inputValue(), "");
  assert.equal(
    await page.evaluate(() => localStorage.length + sessionStorage.length),
    0,
  );
  assert.equal(await page.locator(".t-history-list").count(), 0);
  await page.goto(`${base}/turing/no-such-route`);
  await audit("not-found-390");
  await page.screenshot({
    path: path.join(out, "not-found-390.png"),
    fullPage: true,
  });
  assert.ok(network.every((url) => url.endsWith("/api/v1/quantum/workspace")));
  assert.deepEqual(errors, []);
  const result = {
    scope:
      "Mocked browser transport; NOT native engine, live guardian, provisioning or billing evidence",
    automatedAxeScans: scans,
    checks: [
      "all public routes desktop/mobile",
      "all internal link targets",
      "contact local JSON export, not delivered",
      "no invalid-program submission",
      "same-key retry after ambiguous outcome and auth expiry",
      "same-identity reconnection binding",
      "explicit queued cancellation confirmation",
      "running cancellation refusal",
      "unaltered report JSON download",
      "history pagination/search/status filter/detail",
      "disconnect clears view and credential",
      "no browser storage or mining calls",
    ],
    runtimeErrors: errors,
  };
  fs.writeFileSync(path.join(out, "qa.json"), JSON.stringify(result, null, 2));
  console.log(
    `Passed ${scans.length} accessibility/overflow scans and ${result.checks.length} workflow groups. UI fixtures only.`,
  );
  await browser.close();
  process.exit(0);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

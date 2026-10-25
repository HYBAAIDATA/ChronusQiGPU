/** Isolated UI fixture acceptance, NOT Agent 1 service/browser acceptance.
 * Requires esbuild + playwright available locally; does not install anything.
 */
const { build } = require("esbuild");
const { chromium } = require("playwright");
const fs = require("node:fs");
const path = require("node:path");
const http = require("node:http");
const assert = require("node:assert/strict");
(async () => {
  const root = path.resolve(__dirname, ".."),
    out = path.join(root, "evidence/browser");
  fs.mkdirSync(out, { recursive: true });
  await build({
    entryPoints: [path.join(__dirname, "enterprise_browser_fixture.tsx")],
    outfile: path.join(out, "fixture.js"),
    bundle: true,
    jsx: "automatic",
    format: "iife",
  });
  const html =
    '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>HYBA component fixture — not runtime acceptance</title><link rel="stylesheet" href="/fixture.css"><style>body{margin:0}</style><div id="root"></div><script src="/fixture.js"></script></html>';
  const server = http.createServer((req, res) => {
    res.setHeader("Cache-Control", "no-store");
    if (req.url.startsWith("/fixture.")) {
      const file = path.join(out, req.url.split("?")[0].slice(1));
      res.setHeader(
        "Content-Type",
        file.endsWith(".css") ? "text/css" : "application/javascript",
      );
      res.end(fs.readFileSync(file));
    } else {
      res.setHeader("Content-Type", "text/html");
      res.end(html);
    }
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_PATH || "/usr/local/bin/chromium",
    headless: true,
    args: ["--no-sandbox"],
  });
  const findings = [];
  try {
    for (const scenario of [
      "unbound",
      "success",
      "denied",
      "revoked",
      "expired",
      "failure",
      "unknown",
      "loading",
    ]) {
      const page = await browser.newPage({
        viewport: { width: 1280, height: 1000 },
        reducedMotion: "reduce",
      });
      const errors = [];
      page.on("pageerror", (e) => errors.push(String(e)));
      const external = [];
      page.on("request", (r) => {
        if (!r.url().startsWith(origin)) external.push(r.url());
      });
      await page.goto(origin + "/?scenario=" + scenario);
      if (scenario === "unbound") {
        assert.equal(
          await page.getByRole("button", { name: "Submit backup" }).isEnabled(),
          false,
        );
        await page.keyboard.press("Tab");
        assert.equal(
          await page.locator(":focus").innerText(),
          "Skip to content",
        );
        await page.locator(":focus").blur();
      } else {
        await page
          .getByLabel("Tenant requested")
          .fill(scenario === "denied" ? "denied" : "alpha");
        await page.getByRole("button", { name: "Confirm access" }).click();
        if (scenario === "denied")
          await page
            .getByRole("status")
            .filter({ hasText: "DENIED" })
            .waitFor();
        else if (scenario === "expired")
          await page
            .getByRole("status")
            .filter({ hasText: "EXPIRED" })
            .waitFor();
        else {
          await page.getByLabel("Backup source").setInputFiles({
            name: "fixture.bin",
            mimeType: "application/octet-stream",
            buffer: Buffer.from("fixture only"),
          });
          await page.getByRole("button", { name: "Submit backup" }).click();
          if (["failure", "unknown"].includes(scenario))
            await page
              .getByRole("status")
              .filter({ hasText: scenario.toUpperCase() })
              .waitFor();
          else if (scenario === "loading")
            await page
              .getByRole("status")
              .filter({ hasText: "BUSY" })
              .waitFor();
          else {
            await page
              .getByRole("status")
              .filter({ hasText: "RESULT" })
              .waitFor();
            await page
              .getByLabel("Custody record to restore")
              .fill("FIXTURE-record-42");
            await page
              .getByRole("button", { name: "Verify restore", exact: true })
              .click();
            if (scenario === "revoked") {
              await page
                .getByRole("status")
                .filter({ hasText: "DENIED" })
                .waitFor();
              assert.equal(
                await page
                  .getByText("FIXTURE-alpha-store", { exact: false })
                  .count(),
                0,
              );
            } else {
              await page
                .getByRole("heading", {
                  name: "Digest-matched restore reported",
                })
                .waitFor();
              await page.screenshot({
                path: path.join(out, "success-desktop.png"),
                fullPage: true,
              });
              await page
                .getByText("Inspect service-supplied evidence", { exact: true })
                .click();
              await page.screenshot({
                path: path.join(out, "evidence-expanded-desktop.png"),
                fullPage: true,
              });
              const download = page.waitForEvent("download");
              await page
                .getByRole("button", { name: "Export authorized evidence" })
                .click();
              const received = await download;
              assert.equal(received.suggestedFilename(), "hyba-evidence.json");
              await page.setViewportSize({ width: 390, height: 844 });
              assert.equal(
                await page.evaluate(
                  () => document.documentElement.scrollWidth > innerWidth,
                ),
                false,
              );
              await page.screenshot({
                path: path.join(out, "success-mobile.png"),
                fullPage: true,
              });
              findings.push({
                scenario: "success",
                viewport: "390x844",
                assertions:
                  "passed including evidence expansion and authorized-download fixture",
                scope: "synthetic component only",
              });
              await page.setViewportSize({ width: 1280, height: 1000 });
              await page.getByLabel("Tenant requested").fill("beta");
              assert.equal(
                await page
                  .getByText("FIXTURE-alpha-store", { exact: false })
                  .count(),
                0,
              );
              assert.equal(
                await page.getByLabel("Custody record to restore").inputValue(),
                "",
              );
              assert.equal(
                await page.getByLabel("Backup source").inputValue(),
                "",
              );
            }
          }
        }
      }
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        false,
      );
      assert.deepEqual(errors, []);
      assert.deepEqual(external, []);
      if (scenario !== "success")
        await page.screenshot({
          path: path.join(out, scenario + "-desktop.png"),
          fullPage: true,
        });
      findings.push({
        scenario,
        viewport: "1280x1000",
        assertions: "passed",
        scope: "isolated component with synthetic port double",
        externalRequests: external.length,
      });
      if (scenario === "unbound") {
        await page.setViewportSize({ width: 390, height: 844 });
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth > innerWidth,
          ),
          false,
        );
        await page.screenshot({
          path: path.join(out, "unbound-mobile.png"),
          fullPage: true,
        });
        findings.push({
          scenario,
          viewport: "390x844",
          assertions: "passed",
          scope: "isolated unbound component",
        });
      }
      await page.close();
    }
  } finally {
    await browser.close();
    server.close();
    fs.writeFileSync(
      path.join(out, "results.json"),
      JSON.stringify(
        { scope: "COMPONENT FIXTURE ONLY; no actual service", findings },
        null,
        2,
      ),
    );
  }
  console.log(JSON.stringify(findings, null, 2));
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { createRequire } from "node:module";
import { chromium } from "playwright";
import { createDeveloperServer } from "../scripts/serve.mjs";
const require = createRequire(import.meta.url);
const axeSource = await readFile(
  require.resolve("axe-core/axe.min.js"),
  "utf8",
);
const destination = resolve(
  fileURLToPath(new URL("../../../", import.meta.url)),
  "reports/frontend-developer/browser",
);
await mkdir(destination, { recursive: true });
const server = createDeveloperServer();
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const base = `http://127.0.0.1:${server.address().port}`;
let browser;
const records = [];
try {
  browser = await chromium.launch({
    headless: true,
    ...(process.env.CHROMIUM_PATH
      ? { executablePath: process.env.CHROMIUM_PATH }
      : {}),
  });
  for (const [label, viewport] of [
    ["desktop", { width: 1440, height: 1000 }],
    ["mobile", { width: 390, height: 844 }],
  ]) {
    const context = await browser.newContext({
      viewport,
      reducedMotion: "reduce",
    });
    const page = await context.newPage();
    const runtimeErrors = [],
      requests = [];
    page.on("pageerror", (error) => runtimeErrors.push(error.message));
    page.on("request", (request) => requests.push(request.url()));
    for (const [name, route] of [
      ["overview", "#/"],
      ...["kellogg", "chronus", "ovid", "theseus", "mcp"].map((id) => [
        id,
        `#/components/${id}`,
      ]),
      ["guide", "#/guide"],
      ["not-found", "#/missing"],
    ]) {
      const response = await page.goto(`${base}/?qa=${name}${route}`);
      assert.equal(response.status(), 200);
      await page.locator("h1").waitFor();
      assert.equal(await page.locator("h1").count(), 1);
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        true,
        `${label}/${name} overflow`,
      );
      await page.evaluate(axeSource);
      const accessibility = await page.evaluate(() =>
        axe.run(document, {
          runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
        }),
      );
      assert.deepEqual(
        accessibility.violations.map((v) => ({
          id: v.id,
          nodes: v.nodes.map((n) => n.target),
        })),
        [],
        `${label}/${name} accessibility`,
      );
      for (const href of await page
        .locator("a[href]")
        .evaluateAll((links) => links.map((a) => a.getAttribute("href"))))
        assert(
          href.startsWith("#") ||
            href.startsWith(
              "https://github.com/HYB-APHIDATA/HYBAEnterprise/blob/",
            ),
        );
      const screenshot = `${label}-${name}.png`;
      await page.screenshot({
        path: resolve(destination, screenshot),
        fullPage: true,
      });
      records.push({
        viewport: label,
        route,
        screenshot,
        accessibilityViolations: 0,
      });
    }
    await page.goto(`${base}/#/`);
    await page.getByRole("searchbox").fill("no matching component");
    await page
      .getByRole("heading", { name: "No matching components" })
      .waitFor();
    await page.screenshot({
      path: resolve(destination, `${label}-empty-search.png`),
      fullPage: true,
    });
    await page.getByRole("button", { name: "Clear search" }).click();
    assert.equal(await page.locator(".component-row").count(), 5);
    await page.getByRole("searchbox").fill("custody");
    assert.equal(await page.locator(".component-row").count(), 1);
    await page.getByRole("searchbox").fill('<img src=x onerror="alert(1)">');
    assert.equal(await page.locator("img").count(), 0);
    await page.goto(`${base}/?qa=keyboard#/`);
    await page.locator("h1").waitFor();
    await page.keyboard.press("Tab");
    assert.equal(await page.locator(":focus").innerText(), "Skip to content");
    await page.keyboard.press("Enter");
    await page.waitForFunction(() => document.activeElement?.id === "main");
    await page.getByRole("link", { name: "Read Kellogg reference" }).click();
    await page.waitForFunction(() => document.title === "HYBA — Kellogg");
    assert.equal(await page.locator(":focus").getAttribute("id"), "main");
    await page.goBack();
    await page.waitForFunction(
      () => document.title === "HYBA — Developer components",
    );
    assert.equal(
      await page.evaluate(() => localStorage.length + sessionStorage.length),
      0,
    );
    assert.deepEqual(await context.cookies(), []);
    assert.equal(
      requests.some(
        (url) =>
          !url.startsWith(base) ||
          url.includes("/api/") ||
          url.startsWith("ws:"),
      ),
      false,
    );
    assert.deepEqual(runtimeErrors, []);
    records.push({
      viewport: label,
      states: [
        "empty",
        "filtered",
        "escaped-input",
        "keyboard-skip",
        "route-focus",
        "back-navigation",
      ],
      externalOrApiRequests: 0,
      browserErrors: 0,
    });
    await context.close();
  }
  const nojs = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 390, height: 844 },
  });
  const page = await nojs.newPage();
  await page.goto(base);
  await page.screenshot({
    path: resolve(destination, "mobile-javascript-disabled.png"),
    fullPage: true,
  });
  assert(
    (await page.textContent("body"))
      .replace(/\s+/g, " ")
      .includes("No account or service connection"),
  );
  await nojs.close();
  for (const path of [
    "/api/v1/status",
    "/src/main.tsx",
    "/.vite/manifest.json",
    "/.env",
    "/turing/app",
    "/assets/missing.js",
    "/%2e%2e/%2eenv",
  ])
    assert.equal((await fetch(base + path)).status, 404, path);
  assert.equal((await fetch(base, { method: "POST" })).status, 405);
  assert(
    (await (await fetch(base + "/robots.txt")).text()).includes("Disallow: /"),
  );
  const csp = (await fetch(base)).headers.get("content-security-policy");
  assert(csp.includes("connect-src 'none'"));
  await writeFile(
    resolve(destination, "results.json"),
    JSON.stringify(
      {
        status: "PASS",
        browser: await browser.version(),
        baseline: "b131edc408a37ff7c03534d694bfcdaf0c827abb",
        scope:
          "Production static frontend only; not product execution, private regression, or public GitHub availability",
        records,
      },
      null,
      2,
    ) + "\n",
  );
  console.log(
    `PASS: ${records.length} route/state records; desktop/mobile axe checks; no backend; screenshots retained.`,
  );
} finally {
  await browser?.close();
  await new Promise((resolve) => server.close(resolve));
}

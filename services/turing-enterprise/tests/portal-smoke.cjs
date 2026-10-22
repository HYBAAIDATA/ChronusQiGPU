const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
(async () => {
  const browser = await chromium.launch({
    executablePath:
      process.env.CHROMIUM_PATH ||
      require("playwright").chromium.executablePath(),
    headless: true,
    args: ["--no-sandbox"],
  });
  const root = path.resolve(__dirname, "../src/hyba_turing_service/static");
  const out = process.env.TURING_PREVIEW_DIR || "/tmp/turing-portal-preview";
  fs.mkdirSync(out, { recursive: true });
  let summary = [];
  for (const width of [1280, 390])
    for (const surface of ["workspace", "admin", "ops"]) {
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      const errors = [];
      const submissions = [];
      page.on("pageerror", (e) => errors.push(e.message));
      await page.route("https://turing.test/**", async (route) => {
        const url = new URL(route.request().url());
        let data;
        if (
          url.pathname.endsWith("/jobs") &&
          route.request().method() === "POST"
        ) {
          submissions.push(route.request().postDataJSON());
          return route.fulfill({
            contentType: "application/json",
            body: JSON.stringify({ job: "preview-submit", state: "admitted" }),
          });
        }
        if (url.pathname.startsWith("/assets/"))
          return route.fulfill({
            path: path.join(root, path.basename(url.pathname)),
          });
        if (["/workspace", "/admin", "/ops"].includes(url.pathname))
          return route.fulfill({
            path: path.join(root, "portal.html"),
            contentType: "text/html",
          });
        if (url.pathname === "/api/session")
          data = {
            subject: "design-partner-admin",
            memberships: [{ tenant: "design-partner", role: "admin" }],
            operator: true,
            approver: false,
            csrf: "preview-only",
          };
        else if (url.pathname === "/api/ops/customers")
          data = {
            customers: [
              {
                tenant: "design-partner",
                contract: "pilot-2026",
                state: "active",
                contracted: 3,
                allocated: 2,
                expires: 1795000000,
              },
            ],
          };
        else if (url.pathname === "/api/ops/reconcile")
          data = { issues: [], pending_billing: 0, pending_commercial: 0 };
        else if (url.pathname.endsWith("/overview"))
          data = {
            state: "active",
            allocated: 2,
            available: 1,
            in_flight: 1,
            consumed: 7,
          };
        else if (url.pathname.endsWith("/jobs"))
          data = {
            jobs: [
              {
                job: "bell-check-001",
                state: "admitted",
                actor: "design-partner-admin",
                project: "research",
              },
            ],
          };
        else if (url.pathname.endsWith("/projects"))
          data = {
            projects: [
              { project: "research", slots: 2, allowance: 100, active: 1 },
            ],
          };
        else if (url.pathname.endsWith("/billing"))
          return route.fulfill({
            status: 503,
            body: JSON.stringify({ error: "dependency unavailable" }),
          });
        else if (url.pathname.endsWith("/usage")) data = { usage: [] };
        else if (url.pathname.endsWith("/members")) data = { members: [] };
        else if (url.pathname.endsWith("/audit")) data = { audit: [] };
        else data = { error: "unavailable" };
        return route.fulfill({
          contentType: "application/json",
          body: JSON.stringify(data),
        });
      });
      await page.goto("https://turing.test/" + surface);
      await page.waitForSelector("#app:not([hidden])");
      await page.waitForTimeout(120);
      await page.screenshot({
        path: `${out}/portal-${surface}-${width}.png`,
        fullPage: true,
      });
      let html = await page.content();
      html = html
        .replace(
          '<link rel="stylesheet" href="/assets/portal.css">',
          "<style>" +
            fs.readFileSync(path.join(root, "portal.css"), "utf8") +
            "</style>",
        )
        .replace(/<script[^>]*src="[^"]*"[^>]*><\/script>/g, "");
      fs.writeFileSync(`${out}/portal-${surface}-${width}.html`, html);
      if (await page.locator("#status.error").count())
        throw Error(await page.locator("#status").textContent());
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      );
      summary.push({
        surface,
        width,
        state: "default",
        errors,
        overflow,
        status: await page.locator("#status").textContent(),
      });
      if (surface === "workspace") {
        await page
          .getByLabel("Project identifier", { exact: true })
          .fill("research");
        await page
          .getByLabel("Unique job identifier", { exact: true })
          .fill("preview-submit");
        await page
          .getByRole("button", { name: "Submit governed job", exact: true })
          .click();
        await page.waitForFunction(() =>
          document.getElementById("status").textContent.includes("accepted"),
        );
        if (
          submissions.length !== 1 ||
          submissions[0].request.shots !== 128 ||
          submissions[0].project !== "research"
        )
          throw Error("Portal submission contract mismatch");
      }
      if (surface === "admin") {
        for (const section of ["Projects and capacity", "Operational usage"]) {
          await page
            .getByRole("button", { name: section, exact: true })
            .click();
          await page.waitForTimeout(80);
          await page.screenshot({
            path: `${out}/portal-admin-${section.startsWith("Projects") ? "projects" : "usage"}-${width}.png`,
            fullPage: true,
          });
          if (await page.locator("#status.error").count())
            throw Error(await page.locator("#status").textContent());
          summary.push({
            surface,
            width,
            state: section,
            overflow: await page.evaluate(
              () => document.documentElement.scrollWidth > innerWidth,
            ),
          });
        }
      }
      await page.close();
    }
  fs.writeFileSync(
    path.join(out, "portal-qa.json"),
    JSON.stringify(summary, null, 2),
  );
  await browser.close();
  process.exit(summary.some((x) => x.overflow || x.errors?.length) ? 1 : 0);
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

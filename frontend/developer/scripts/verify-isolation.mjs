import { execFileSync } from "node:child_process";
import { readFile, writeFile, mkdir, rm } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
const frontend = fileURLToPath(new URL("../../", import.meta.url));
const main = resolve(frontend, "developer/src/main.tsx");
const original = await readFile(main, "utf8");
const canaryDir = resolve(frontend, "developer/public");
const reports = resolve(frontend, "../reports/frontend-developer");
await mkdir(reports, { recursive: true });
const build = () =>
  execFileSync(
    process.execPath,
    [
      resolve(frontend, "node_modules/vite/bin/vite.js"),
      "build",
      "--config",
      "vite.developer.config.ts",
    ],
    {
      cwd: frontend,
      env: {
        ...process.env,
        VITE_PRIVATE_BUILD_CANARY: "HYBA_PRIVATE_BUILD_CANARY",
        PYTHIA_API_URL: "http://127.0.0.1:1",
      },
      encoding: "utf8",
      stdio: "pipe",
    },
  );
let privateImportRejected = false;
try {
  await writeFile(main, `${original}\nimport '../../src/App.tsx';\n`);
  try {
    build();
  } catch (error) {
    const output = `${error.stdout ?? ""}\n${error.stderr ?? ""}`;
    if (!output.includes("Developer build refused an unapproved module"))
      throw error;
    privateImportRejected = true;
  }
  if (!privateImportRejected)
    throw new Error("Private module unexpectedly entered the graph");
} finally {
  await writeFile(main, original);
}
try {
  await mkdir(canaryDir, { recursive: true });
  await writeFile(
    resolve(canaryDir, "private-canary.txt"),
    "HYBA_PRIVATE_BUILD_CANARY",
  );
  build();
  execFileSync(process.execPath, ["developer/scripts/audit-output.mjs"], {
    cwd: frontend,
    stdio: "pipe",
  });
  const injected = resolve(
    frontend,
    "../dist/developer/assets/negative-check.js",
  );
  try {
    await writeFile(injected, "HYBA_PRIVATE_BUILD_CANARY");
    let rejected = false;
    try {
      execFileSync(process.execPath, ["developer/scripts/audit-output.mjs"], {
        cwd: frontend,
        stdio: "pipe",
      });
    } catch (error) {
      if (!String(error.stderr).includes("Public output policy violation"))
        throw error;
      rejected = true;
    }
    if (!rejected) throw new Error("Output canary not rejected");
  } finally {
    await rm(injected, { force: true });
  }
  const outputAudit = JSON.parse(
    execFileSync(process.execPath, ["developer/scripts/audit-output.mjs"], {
      cwd: frontend,
      encoding: "utf8",
    }),
  );
  await writeFile(
    resolve(reports, "isolation.json"),
    JSON.stringify(
      {
        status: "PASS",
        privateImportRejected,
        publicDirectoryCanaryExcluded: true,
        environmentCanaryExcluded: true,
        outputCanaryRejected: true,
        outputAudit,
      },
      null,
      2,
    ) + "\n",
  );
  console.log(
    "PASS: private import rejected; publicDir/env canaries excluded; output canary rejected.",
  );
} finally {
  await rm(resolve(canaryDir, "private-canary.txt"), { force: true });
}

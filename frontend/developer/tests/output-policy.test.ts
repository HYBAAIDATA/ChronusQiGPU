import { describe, expect, it } from "vitest";
// @ts-expect-error Policy is shared with the dependency-free Node artifact audit.
import { inspectAsset } from "../scripts/output-policy.mjs";
describe("output policy", () => {
  it.each([
    "mining",
    "Stratum",
    "/api/auth/login",
    "VITE_PYTHIA_PYTHON_API_URL",
    "HYBA_PRIVATE_BUILD_CANARY",
    "//# sourceMappingURL=private.map",
    "-----BEGIN PRIVATE KEY-----",
  ])("rejects %s", (text) =>
    expect(() => inspectAsset("assets/main.js", text)).toThrow(),
  );
  it("rejects source maps and unreviewed media", () => {
    expect(() => inspectAsset("main.js.map", "{}")).toThrow();
    expect(() => inspectAsset("private.png", "")).toThrow();
  });
  it("accepts a safe text artifact", () =>
    expect(() => inspectAsset("index.html", "<h1>Kellogg</h1>")).not.toThrow());
});

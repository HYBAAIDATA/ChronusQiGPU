import { describe, expect, it } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { developerBoundary } from "../../vite.developer.config";

const root = resolve(import.meta.dirname, "..");
function files(path: string): string[] {
  return readdirSync(path, { withFileTypes: true }).flatMap((entry) =>
    entry.isDirectory()
      ? files(resolve(path, entry.name))
      : [resolve(path, entry.name)],
  );
}
describe("public source policy", () => {
  it("has no runtime service, secret store or external embedded resource", () => {
    for (const file of files(resolve(root, "src"))) {
      const text = readFileSync(file, "utf8");
      expect(text, file).not.toMatch(
        /\bfetch\s*\(|XMLHttpRequest|WebSocket|EventSource|localStorage|sessionStorage|document\.cookie|import\.meta\.env|dangerouslySetInnerHTML/,
      );
      expect(text, file).not.toMatch(/\bmining\b|pythia|stratum|mla1517/i);
      for (const match of text.matchAll(
        /(?:from|import)\s*["']([^"']+)["']/g,
      )) {
        if (match[1] === "../../../../docs/brand/hyba_tokens.css") continue;
        expect(match[1], file).not.toMatch(
          /\/lib\/|\/turing\/|\/components\/Control|\.\.\/\.\.\/\.\./,
        );
      }
    }
  });
  it("retains separate public and private outputs and disables asset copying", () => {
    const config = readFileSync(
      resolve(root, "../vite.developer.config.ts"),
      "utf8",
    );
    expect(config).toContain('"../dist/developer"');
    expect(config).toContain("publicDir: false");
    expect(config).toContain("sourcemap: false");
    expect(config).toContain("envPrefix: []");
    expect(readFileSync(resolve(root, "../vite.config.ts"), "utf8")).toContain(
      'outDir: "../dist/public"',
    );
  });
  it("rejects private and unapproved graph imports at build time", () => {
    const plugin = developerBoundary();
    const load = plugin.load as (
      this: { error: (s: string) => never },
      id: string,
    ) => null;
    const context = {
      error: (message: string): never => {
        throw new Error(message);
      },
    };
    for (const id of [
      resolve(root, "../src/App.tsx"),
      resolve(root, "../src/lib/api.ts"),
      resolve(root, "../../.env"),
      resolve(root, "../src/turing/TuringApp.tsx"),
    ]) {
      expect(() => load.call(context, id)).toThrow("unapproved module");
    }
    expect(load.call(context, resolve(root, "src/main.tsx"))).toBeNull();
  });
});

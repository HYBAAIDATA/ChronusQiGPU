import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { describe, expect, it } from "vitest";
/** Follow local static imports from the live mining console, not test fixtures
 * or the separately routed TURING app. Legitimate reference math is not telemetry. */
function sources(path: string, seen = new Set<string>()): Map<string,string> {
  const files = new Map<string,string>();
  if (seen.has(path)) return files; seen.add(path);
  const text=readFileSync(path,"utf8");files.set(path,text);
  for (const match of text.matchAll(/from\s+["'](\.[^"']+)["']/g)) {
    const base=resolve(dirname(path),match[1]);
    for (const ext of ["", ".ts", ".tsx"]) {
      try { for (const [k,v] of sources(base+ext,seen)) files.set(k,v); break; } catch { /* try next source extension */ }
    }
  }
  return files;
}
function violations(text:string) {
  return [ /Math\.random\(/, /simulate(?:d)?(?:Hashrate|Shares|Telemetry)/i,
    /(?:hashrate|shares_accepted|attempts_total|counters\?\.\w+)\s*\?\?\s*\d/,
    /\blocalStorage\s*(?:\.|\[)/, /runAudit\(/, /requestAnimationFrame\(/ ].filter(pattern => pattern.test(text));
}
describe("live console no-mock boundary", () => {
  it("rejects seeded fake telemetry and stale truth paths", () => {
    expect(violations("const hashrate = source.hashrate ?? 508000000")).toHaveLength(1);
    expect(violations("Math.random() * 100")).toHaveLength(1);
    expect(violations("window.localStorage.getItem(key)")).toHaveLength(1);
  });
  it("keeps local calculators and simulated manifold out of the rendered graph", () => {
    const graph=sources(resolve("src/App.tsx"));expect(graph.size).toBeGreaterThan(10);
    for (const [path,text] of graph) expect(violations(text), path).toEqual([]);
    expect([...graph.keys()].some(p => /views\/(Audit|Algebra|Manifold)View/.test(p))).toBe(false);
  });
});

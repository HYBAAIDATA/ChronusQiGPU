import { describe, expect, it } from "vitest";
import {
  COMPONENTS,
  COMPONENT_IDS,
  findComponent,
  sourceUrl,
  SOURCE_REVISION,
} from "../src/catalog";
import { resolveRoute } from "../src/routes";

describe("release scope", () => {
  it("contains exactly the five approved components", () => {
    expect(COMPONENTS.map((c) => c.id)).toEqual([
      "kellogg",
      "chronus",
      "ovid",
      "theseus",
      "mcp",
    ]);
    expect(new Set(COMPONENTS.map((c) => c.id)).size).toBe(5);
  });
  it.each(COMPONENT_IDS)(
    "has explicit boundaries and qualification limits for %s",
    (id) => {
      const component = findComponent(id)!;
      for (const key of [
        "owns",
        "boundary",
        "interface",
        "compatibility",
        "limitation",
      ] as const)
        expect(component[key].length).toBeGreaterThan(30);
      expect(["Source inspected", "Publication review"]).toContain(
        component.status,
      );
    },
  );
  it("keeps MCP identity and deployment honest", () => {
    expect(findComponent("mcp")?.owns).toContain("hyba-mcp-server");
    expect(findComponent("mcp")?.status).toBe("Publication review");
    expect(findComponent("mcp")?.references).toEqual([]);
  });
  it("pins actual repository references", () => {
    expect(SOURCE_REVISION).toMatch(/^[a-f0-9]{40}$/);
    for (const component of COMPONENTS)
      for (const ref of component.references) {
        const url = new URL(sourceUrl(ref.path));
        expect(url.origin).toBe("https://github.com");
        expect(url.pathname).toContain(
          `/HYB-APHIDATA/HYBAEnterprise/blob/${SOURCE_REVISION}/`,
        );
        expect(ref.path).not.toMatch(/(?:^\/|\.\.|mining|Intelligence|\.env)/);
      }
  });
  it("does not invent installations or release downloads", () => {
    expect(JSON.stringify(COMPONENTS)).not.toMatch(
      /pip install|npm install|registry\.npmjs|pypi\.org|releases\/download/,
    );
  });
});
describe("static routing", () => {
  it.each(["", "#", "#/", "#///"])("resolves home %s", (hash) =>
    expect(resolveRoute(hash)).toEqual({ kind: "overview" }),
  );
  it.each(COMPONENT_IDS)("resolves the %s reference", (id) =>
    expect(resolveRoute(`#/components/${id}/`)).toEqual({
      kind: "component",
      id,
    }),
  );
  it("resolves the guide", () =>
    expect(resolveRoute("#/guide")).toEqual({ kind: "guide" }));
  it.each([
    "#/components/nope",
    "#/turing",
    "#/operations",
    "#/../src",
    "#/%3Cscript%3E",
    "#https://other.example",
  ])("refuses unknown route %s", (hash) =>
    expect(resolveRoute(hash)).toEqual({ kind: "not-found" }),
  );
});

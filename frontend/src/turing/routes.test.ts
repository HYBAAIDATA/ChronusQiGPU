import { describe, expect, it } from "vitest";
import { PUBLIC_PAGES, resolveTuringRoute } from "./routes";
import { ARTICLES } from "./productContent";
describe("TURING namespace and publication boundaries", () => {
  it.each(["/turing", "/turing/", "/turing/app"])(
    "preserves evaluation workspace %s",
    (path) => expect(resolveTuringRoute(path).kind).toBe("workspace"),
  );
  it.each([...PUBLIC_PAGES])("resolves supported article %s", (page) =>
    expect(resolveTuringRoute(`/turing/${page}/`)).toEqual({
      kind: "public",
      page,
    }),
  );
  it.each([
    "/",
    "/app",
    "/turingevil",
    "/turing/ops/customers",
    "/turing/org/acme/billing",
    "/turing/unknown",
  ])("does not imply an unsupported administration capability %s", (path) =>
    expect(resolveTuringRoute(path).kind).toBe("not-found"),
  );
  it("has substantive sourced copy for every non-interactive public article", () => {
    for (const page of PUBLIC_PAGES) {
      if (page === "product" || page === "contact") continue;
      expect(ARTICLES[page].sections.length).toBeGreaterThan(1);
      expect(ARTICLES[page].intro.length).toBeGreaterThan(60);
    }
  });
});

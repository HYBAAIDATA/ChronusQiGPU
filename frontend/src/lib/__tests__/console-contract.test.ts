import { describe, expect, it } from "vitest";
import fixture from "../../../contracts/console.fixture.json";
import schema from "../../../contracts/console.schema.json";
import { parseConsoleStatus } from "../console";
describe("Python-produced console wire envelope", () => {
  it("accepts a current-source producer document validated by Pydantic", () => {
    const status = parseConsoleStatus(fixture);
    expect(status.ready_to_mine?.ready).toBe(false);
    expect(Object.keys(status.console!).sort()).toEqual(Object.keys(schema.$defs.ConsoleSources.properties).sort());
  });
  it.each([null, [], { schema_version: "fake" }, { ...fixture, ready_to_mine: { ready: "true" } }])("rejects malformed verdict %j", value => expect(() => parseConsoleStatus(value)).toThrow());
});

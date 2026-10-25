import { COMPONENT_IDS, type ComponentId } from "./catalog";
export type Route =
  | { kind: "overview" }
  | { kind: "component"; id: ComponentId }
  | { kind: "guide" }
  | { kind: "not-found" };
/** Hash routes work on static hosts and subpaths without a history-fallback rewrite. */
export function resolveRoute(hash: string): Route {
  const path = hash.replace(/^#/, "").replace(/\/+$/, "") || "/";
  if (path === "/") return { kind: "overview" };
  if (path === "/guide") return { kind: "guide" };
  const id = path.replace(/^\/components\//, "");
  return path.startsWith("/components/") &&
    (COMPONENT_IDS as readonly string[]).includes(id)
    ? { kind: "component", id: id as ComponentId }
    : { kind: "not-found" };
}

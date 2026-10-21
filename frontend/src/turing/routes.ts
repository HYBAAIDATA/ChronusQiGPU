export const PUBLIC_PAGES = [
  "product",
  "capabilities",
  "how-it-works",
  "enterprise",
  "documentation",
  "security",
  "research",
  "contact",
  "legal/privacy",
  "legal/terms",
] as const;
export type PublicPage = (typeof PUBLIC_PAGES)[number];
export type TuringRoute =
  | { kind: "workspace" }
  | { kind: "public"; page: PublicPage }
  | { kind: "not-found" };
/** Namespace preserves the existing mining product and its root route. */
export function resolveTuringRoute(pathname: string): TuringRoute {
  const path = pathname.replace(/\/+$/, "");
  if (path === "/turing" || path === "/turing/app")
    return { kind: "workspace" };
  const page = path.replace(/^\/turing\//, "");
  return (PUBLIC_PAGES as readonly string[]).includes(page) &&
    path.startsWith("/turing/")
    ? { kind: "public", page: page as PublicPage }
    : { kind: "not-found" };
}

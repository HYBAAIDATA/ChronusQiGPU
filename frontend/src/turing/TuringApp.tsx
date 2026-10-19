import Workspace from "./Workspace";
import PublicSite from "./PublicSite";
import { resolveTuringRoute } from "./routes";
export default function TuringApp() {
  const route = resolveTuringRoute(window.location.pathname);
  return route.kind === "workspace" ? (
    <Workspace />
  ) : (
    <PublicSite page={route.kind === "public" ? route.page : null} />
  );
}

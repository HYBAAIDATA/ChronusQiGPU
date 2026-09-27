/**
 * RETIRED: browser MiningEngine / mock Stratum path.
 *
 * All operator UI state must come from the live Python control API via
 * `useBackend` in `./backend-store`. This module remains only as a thin
 * compatibility re-export so any residual import resolves to the live path.
 */

export { useBackend as useMining } from "./backend-store";
export type { BackendState as MiningView } from "./backend-store";

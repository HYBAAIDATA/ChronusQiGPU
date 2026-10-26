import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

const frontend = fileURLToPath(new URL(".", import.meta.url));
const root = resolve(frontend, "developer");
const source = resolve(root, "src");
const dependencies = resolve(frontend, "node_modules");
const tokens = resolve(frontend, "../docs/brand/hyba_tokens.css");
const inside = (id: string, dir: string) =>
  id === dir || id.startsWith(`${dir}/`);

/** Enforce the build graph, rather than concealing private routes at runtime. */
export function developerBoundary(): Plugin {
  return {
    name: "hyba-developer-boundary",
    enforce: "pre",
    load(id) {
      const file = id.split("?")[0];
      if (!file.startsWith("/") || file.startsWith("/@")) return null;
      if (
        inside(file, source) ||
        inside(file, dependencies) ||
        file === tokens ||
        file === resolve(root, "index.html")
      )
        return null;
      this.error(`Developer build refused an unapproved module: ${file}`);
    },
    generateBundle(_options, bundle) {
      for (const asset of Object.values(bundle)) {
        if (asset.type !== "chunk") continue;
        for (const id of Object.keys(asset.modules)) {
          const file = id.replace(/^\0/, "").split("?")[0];
          if (!file.startsWith("/")) continue;
          if (
            !inside(file, source) &&
            !inside(file, dependencies) &&
            file !== tokens &&
            file !== resolve(root, "index.html")
          ) {
            this.error(
              `Developer output contains an unapproved module: ${file}`,
            );
          }
        }
      }
    },
  };
}

export default defineConfig({
  root,
  base: "./",
  publicDir: false,
  envPrefix: [],
  plugins: [developerBoundary(), react()],
  build: {
    outDir: resolve(frontend, "../dist/developer"),
    emptyOutDir: true,
    sourcemap: false,
    manifest: true,
  },
  server: {
    host: "127.0.0.1",
    fs: { strict: true, allow: [root, dependencies, tokens] },
    // No proxy, backend discovery, authentication or API client in this build.
  },
  preview: { host: "127.0.0.1" },
});

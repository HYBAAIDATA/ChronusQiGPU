import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const rootDir = fileURLToPath(new URL(".", import.meta.url));

function processAlive(pid: unknown): boolean {
  if (typeof pid !== "number" || !Number.isInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return (error as NodeJS.ErrnoException).code === "EPERM";
  }
}

/**
 * Where the dev server proxies /api: PYTHIA_API_URL, else the port the
 * running control API published (PYTHIA_ACTIVE_PORTS_FILE, default
 * /tmp/hyba_active_ports.json) while its process is alive, else PYTHIA_PORT
 * or 3000 on loopback.
 */
function pythonApiTarget(): string {
  const explicit = process.env.PYTHIA_API_URL?.trim();
  if (explicit) return explicit.replace(/\/$/, "");
  const portsFile = process.env.PYTHIA_ACTIVE_PORTS_FILE || "/tmp/hyba_active_ports.json";
  try {
    if (existsSync(portsFile)) {
      const ports = JSON.parse(readFileSync(portsFile, "utf-8")) as Record<string, unknown>;
      if (typeof ports.python_url === "string" && processAlive(ports.python_pid)) {
        return ports.python_url.replace(/\/$/, "");
      }
    }
  } catch {
    // Unreadable port file: fall through to the configured port.
  }
  return `http://127.0.0.1:${process.env.PYTHIA_PORT || "3000"}`;
}

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  build: {
    // Backend contract is unchanged: main.py --web-root dist/public.
    outDir: "../dist/public",
    sourcemap: false,
    emptyOutDir: true,
  },
  server: {
    // HMR is disabled in AI Studio via DISABLE_HMR env var.
    // Do not modify—file watching is disabled to prevent flickering during agent edits.
    hmr: process.env.DISABLE_HMR !== "true",
    // Disable file watching when DISABLE_HMR is true to save CPU during agent edits.
    watch: process.env.DISABLE_HMR === "true" ? null : {},
    // Same-origin /api in dev, exactly as main.py serves it in production.
    proxy: { "/api": { target: pythonApiTarget(), changeOrigin: false } },
  },
});

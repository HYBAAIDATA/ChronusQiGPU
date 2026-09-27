import { defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config";

export default mergeConfig(
  viteConfig as unknown as Parameters<typeof mergeConfig>[0],
  defineConfig({
    test: {
      environment: "jsdom",
      // node_modules resolves one level up (repo root); the forks pool's
      // worker spawn can't resolve that layout on Windows — threads can.
      pool: "threads",
      include: ["src/**/*.{test,spec}.{ts,tsx}"],
      clearMocks: true,
      restoreMocks: true,
      coverage: {
        provider: "v8",
        reporter: ["text", "json", "html"],
        include: ["src/**/*.{ts,tsx}"],
        exclude: ["src/test/**", "src/main.tsx", "src/vite-env.d.ts"],
        thresholds: {
          perFile: true,
          lines: 81,
          functions: 80,
          branches: 80,
          statements: 80,
        },
      },
    },
  }),
);

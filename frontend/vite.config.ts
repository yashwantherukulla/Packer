/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    proxy: {
      // FastAPI serves /pack, /detect, ... at the root; strip the /api prefix.
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    css: false,
    // Vitest owns the unit/component suite under src/ only. The Playwright E2E
    // specs live in e2e/ and run via `npm run e2e` (they use @playwright/test's
    // own runner, not Vitest) — scope include so they never leak into the unit gate.
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
  },
});

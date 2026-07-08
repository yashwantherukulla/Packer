import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000, // pack trains a tiny model on CPU
  expect: { timeout: 60_000 },
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5173", trace: "on-first-retry" },
  // No webServer: the full stack (API+workers+redis+pg+frontend) is brought up via docker compose (Phase 6).
});

import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 15 * 60 * 1000, // pack training dominates the chain spec; be generous (flaky-E2E risk)
  expect: { timeout: 30_000 },
  retries: process.env.CI ? 1 : 0, // retry only infra flake, never assertion failures
  use: {
    // PACKER_E2E_FRONTEND_URL aligns with the Python harness (tests/e2e/conftest.py);
    // E2E_BASE_URL kept as a fallback for the Phase-5 happy-path specs.
    baseURL:
      process.env.PACKER_E2E_FRONTEND_URL ?? process.env.E2E_BASE_URL ?? "http://localhost:5173",
    trace: "on-first-retry",
    video: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  // No webServer: the full stack (API+workers+redis+pg+frontend) is brought up via docker compose.
});

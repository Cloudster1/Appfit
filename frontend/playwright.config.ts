import { defineConfig, devices } from "@playwright/test";

const TIMEOUT_MS = 90_000;

export default defineConfig({
  testDir: "./e2e",
  timeout: TIMEOUT_MS,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:8080",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});

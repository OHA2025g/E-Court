import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    baseURL: process.env.PMIS_BASE_URL || "http://localhost:5182",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      testIgnore: ["**/workflow-gating.spec.js", "**/bulk-upload.spec.js"],
      grepInvert: /Task workflow lifecycle/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "submission-flow",
      testMatch: ["**/workflow-gating.spec.js", "**/bulk-upload.spec.js"],
      fullyParallel: false,
      workers: 1,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "task-workflow",
      testMatch: ["**/task-management.spec.js"],
      grep: /Task workflow lifecycle/,
      fullyParallel: false,
      workers: 1,
      timeout: 120_000,
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});

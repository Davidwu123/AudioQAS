import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  outputDir: ".tmp/test-results",
  timeout: 30000,
  retries: 0,
  use: {
    headless: true,
    viewport: { width: 1280, height: 900 },
    locale: "zh-CN",
    baseURL: "http://localhost:8765",
  },
  webServer: {
    command: "python3 -m http.server 8765",
    port: 8765,
    reuseExistingServer: true,
    timeout: 10000,
  },
  projects: [
    {
      name: "chromium",
      use: { browserName: "chromium" },
    },
  ],
});

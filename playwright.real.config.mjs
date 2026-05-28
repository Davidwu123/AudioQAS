import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: /web_preview_real_backend\.spec\.mjs/,
  outputDir: ".tmp/test-results-real",
  timeout: 120000,
  retries: 0,
  use: {
    headless: true,
    viewport: { width: 1280, height: 900 },
    locale: "zh-CN",
    baseURL: "http://127.0.0.1:8010",
  },
  webServer: {
    command: ".venv/bin/python -m audioqas.web.run_local",
    port: 8010,
    reuseExistingServer: false,
    timeout: 120000,
    env: {
      AUDIOQAS_WEB_HOST: "127.0.0.1",
      AUDIOQAS_WEB_PORT: "8010",
      AUDIOQAS_WEB_RELOAD: "0",
      AUDIOQAS_PREPROCESS_DIR: ".tmp/e2e-real/preprocessed",
      AUDIOQAS_WEB_STATE_DIR: ".tmp/e2e-real/web_state",
      AUDIOQAS_LOG_DIR: ".tmp/e2e-real/log",
    },
  },
  projects: [
    {
      name: "chromium-real-backend",
      use: { browserName: "chromium" },
    },
  ],
});

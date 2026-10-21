import { defineConfig } from "@playwright/test";

const PORT = 5173;

export default defineConfig({
  testDir: "tests-smoke",
  timeout: 30000,
  use: {
    baseURL: `http://localhost:${PORT}/`,
    browserName: "chromium",
  },
  webServer: {
    command: "npm run dev",
    url: `http://localhost:${PORT}/`,
    reuseExistingServer: true,
    timeout: 60000,
  },
});

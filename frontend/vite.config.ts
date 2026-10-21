import { defineConfig, configDefaults } from "vitest/config";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Backend dev server is Agent A's FastAPI app; default vite proxy target.
    proxy: {
      "/api": "http://localhost:8000"
    }
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/tests/setup.ts",
    css: true,
    exclude: [...configDefaults.exclude, "tests-smoke/**"]
  }
});

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

import { DEV_WATCH_POLL_MS } from "./src/config.ts";

const apiTarget = process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": { target: apiTarget, changeOrigin: false } },
    watch: process.env.CHOKIDAR_USEPOLLING ? { usePolling: true, interval: DEV_WATCH_POLL_MS } : undefined,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
  },
});

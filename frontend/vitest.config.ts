import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * Vitest config for the unit/integration suite.
 *
 * - jsdom so DOM-touching code (hooks, the axios XHR adapter, MSW XHR interception)
 *   runs without a browser.
 * - The `@/*` alias mirrors tsconfig's paths so test imports match app imports.
 * - `setupFiles` wires jest-dom matchers + the MSW server lifecycle once per run.
 */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    css: false,
    restoreMocks: true,
  },
});

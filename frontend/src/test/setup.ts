/**
 * Global test setup: jest-dom matchers + MSW server lifecycle.
 *
 * `onUnhandledRequest: "error"` makes any un-mocked network call fail loudly so a
 * test never silently hits a real backend. Individual tests layer endpoint-specific
 * handlers via `server.use(...)`; `resetHandlers` clears them between tests.
 */
import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "./msw/server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));

afterEach(() => {
  cleanup();
  server.resetHandlers();
});

afterAll(() => server.close());

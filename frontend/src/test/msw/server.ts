/** MSW node server for the test suite. Tests add per-case handlers via `server.use()`. */
import { setupServer } from "msw/node";

import { handlers } from "./handlers";

export const server = setupServer(...handlers);

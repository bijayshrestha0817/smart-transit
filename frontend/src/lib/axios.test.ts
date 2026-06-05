import { describe, expect, it } from "vitest";

import { API, fail, http, ok } from "@/test/msw/handlers";
import { server } from "@/test/msw/server";

import { api } from "./axios";

describe("axios 401 → refresh interceptor", () => {
  it("refreshes once for concurrent 401s, then retries (single-flight)", async () => {
    let authed = false;
    let refreshCount = 0;

    server.use(
      http.get(`${API}/protected/`, () =>
        authed ? ok({ ok: true }) : fail(401, "unauthenticated"),
      ),
      http.post(`${API}/auth/refresh/`, () => {
        refreshCount += 1;
        authed = true;
        return ok(null);
      }),
    );

    const [a, b] = await Promise.all([api.get("/protected/"), api.get("/protected/")]);

    // Both concurrent 401s share ONE refresh, then both replay successfully.
    expect(refreshCount).toBe(1);
    expect(a.data.data).toEqual({ ok: true });
    expect(b.data.data).toEqual({ ok: true });
  });

  it("never tries to refresh a 401 from the refresh endpoint itself", async () => {
    let refreshCount = 0;
    server.use(
      http.post(`${API}/auth/refresh/`, () => {
        refreshCount += 1;
        return fail(401, "token_invalid");
      }),
    );

    await expect(api.post("/auth/refresh/")).rejects.toMatchObject({
      response: { status: 401 },
    });
    // Bypassed endpoint -> exactly one hit, no refresh-of-refresh loop.
    expect(refreshCount).toBe(1);
  });

  it("rejects (no retry) on a non-401 error", async () => {
    let hits = 0;
    server.use(
      http.get(`${API}/widgets/`, () => {
        hits += 1;
        return fail(500, "server_error");
      }),
    );

    await expect(api.get("/widgets/")).rejects.toMatchObject({
      response: { status: 500 },
    });
    expect(hits).toBe(1);
  });
});

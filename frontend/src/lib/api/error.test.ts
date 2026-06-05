import { AxiosError, type AxiosResponse } from "axios";
import { describe, expect, it } from "vitest";

import { ApiError, toApiError, unwrap, unwrapPage } from "./error";
import type { ApiEnvelope, PaginatedEnvelope } from "./types";

/** Build a minimal AxiosError carrying an enveloped error body at `status`. */
function axiosErrorWithBody(status: number, body: unknown): AxiosError {
  const response = { status, data: body } as AxiosResponse;
  return new AxiosError("request failed", "ERR_BAD_RESPONSE", undefined, {}, response);
}

describe("toApiError", () => {
  it("extracts code/status/detail from an enveloped error body", () => {
    const err = toApiError(
      axiosErrorWithBody(400, {
        data: null,
        meta: null,
        errors: [{ code: "invalid_near", field: "near", detail: "Bad coordinate" }],
      }),
    );
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("invalid_near");
    expect(err.status).toBe(400);
    expect(err.message).toBe("Bad coordinate");
    expect(err.has("invalid_near")).toBe(true);
    expect(err.fieldError("near")).toBe("Bad coordinate");
  });

  it("maps a transport failure (no response) to a network_error", () => {
    const err = toApiError(new AxiosError("Network Error", "ERR_NETWORK"));
    expect(err.code).toBe("network_error");
    expect(err.status).toBe(0);
  });

  it("passes an existing ApiError through unchanged", () => {
    const original = new ApiError("boom", "x", 500, []);
    expect(toApiError(original)).toBe(original);
  });

  it("wraps a non-axios throw as an unknown error", () => {
    const err = toApiError(new Error("kaboom"));
    expect(err.code).toBe("unknown");
    expect(err.status).toBe(0);
  });
});

describe("unwrap", () => {
  it("returns the data payload on success", () => {
    const env: ApiEnvelope<{ id: number }> = { data: { id: 7 }, meta: null, errors: null };
    expect(unwrap(env)).toEqual({ id: 7 });
  });

  it("throws an ApiError when the envelope carries errors", () => {
    const env: ApiEnvelope<null> = {
      data: null,
      meta: null,
      errors: [{ code: "required", field: "name", detail: "This field is required." }],
    };
    expect(() => unwrap(env)).toThrowError(ApiError);
  });
});

describe("unwrapPage", () => {
  it("splits a paginated envelope into rows + pagination", () => {
    const env: PaginatedEnvelope<{ id: number }> = {
      data: [{ id: 1 }, { id: 2 }],
      meta: { pagination: { next: "http://x/?cursor=abc", prev: null, page_size: 20 } },
      errors: null,
    };
    const { rows, pagination } = unwrapPage(env);
    expect(rows).toHaveLength(2);
    expect(pagination.next).toContain("cursor=abc");
    expect(pagination.page_size).toBe(20);
  });
});

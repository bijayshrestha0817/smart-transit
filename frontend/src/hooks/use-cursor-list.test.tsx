import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { useCursorList } from "./use-cursor-list";

interface Row {
  id: number;
}

const PAGE1 = {
  rows: [{ id: 1 }],
  pagination: {
    next: "http://localhost:8000/api/v1/routes/?cursor=CUR2",
    prev: null,
    page_size: 20,
  },
};
const PAGE2 = {
  rows: [{ id: 2 }],
  pagination: {
    next: null,
    prev: "http://localhost:8000/api/v1/routes/?cursor=CUR1",
    page_size: 20,
  },
};

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

describe("useCursorList", () => {
  it("extracts the opaque cursor token from the absolute next URL on next()", async () => {
    // Page 2 is keyed off the token parsed out of PAGE1.pagination.next (CUR2).
    const fetchPage = vi.fn(async ({ cursor }: { cursor?: string }) =>
      cursor === "CUR2" ? PAGE2 : PAGE1,
    );

    const { result } = renderHook(
      () => useCursorList<Row, { search: string }>({ queryKey: ["routes"], params: { search: "a" }, fetchPage }),
      { wrapper: makeWrapper() },
    );

    await waitFor(() => expect(result.current.rows).toEqual([{ id: 1 }]));
    expect(result.current.hasNext).toBe(true);

    act(() => result.current.next());

    await waitFor(() => expect(result.current.rows).toEqual([{ id: 2 }]));
    expect(fetchPage).toHaveBeenLastCalledWith(
      expect.objectContaining({ cursor: "CUR2", search: "a" }),
    );
  });

  it("resets to the first page (cursor cleared) when params change", async () => {
    const fetchPage = vi.fn(async ({ cursor }: { cursor?: string }) =>
      cursor === "CUR2" ? PAGE2 : PAGE1,
    );

    const { result, rerender } = renderHook(
      ({ search }: { search: string }) =>
        useCursorList<Row, { search: string }>({ queryKey: ["routes"], params: { search }, fetchPage }),
      { wrapper: makeWrapper(), initialProps: { search: "a" } },
    );

    await waitFor(() => expect(result.current.rows).toEqual([{ id: 1 }]));
    act(() => result.current.next());
    await waitFor(() => expect(result.current.rows).toEqual([{ id: 2 }]));

    // Changing the filter must drop the stale cursor (else the backend 404s it).
    rerender({ search: "b" });

    await waitFor(() => expect(result.current.rows).toEqual([{ id: 1 }]));
    const lastArgs = fetchPage.mock.lastCall?.[0];
    expect(lastArgs).toMatchObject({ search: "b" });
    expect(lastArgs?.cursor).toBeUndefined();
  });
});

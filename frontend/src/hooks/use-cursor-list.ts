"use client";

/**
 * Generic hook for the backend's cursor-paginated list endpoints.
 *
 * Implementation rules (from the P1 plan):
 *  1. NEVER send the absolute `next`/`prev` URL back through `api` — the axios
 *     instance already has `/api/v1` as its baseURL. We extract the opaque cursor
 *     token from the URL and re-issue the RELATIVE endpoint with `{ cursor }`.
 *  2. A cursor is only valid for the ordering/filters it was minted under, so any
 *     change to `params` resets to page 1 (else the backend 404s "Invalid cursor").
 */

import { useState } from "react";
import { useQuery, type QueryKey } from "@tanstack/react-query";

import type { PaginationMeta } from "@/lib/api/types";

interface Page<T> {
  rows: T[];
  pagination: PaginationMeta;
}

interface UseCursorListArgs<T, P extends Record<string, unknown>> {
  /** Stable base key for this list (e.g. `QUERY_KEYS.adminRoutes(params)`). */
  queryKey: QueryKey;
  /** Filter/sort/search params — NOT the cursor. */
  params: P;
  /** Fetches one page against the relative endpoint. */
  fetchPage: (args: P & { cursor?: string }) => Promise<Page<T>>;
  enabled?: boolean;
}

/** Read the opaque `?cursor` token out of an absolute URL (never decoded). */
function cursorOf(url: string | null | undefined): string | undefined {
  if (!url) return undefined;
  try {
    return new URL(url).searchParams.get("cursor") ?? undefined;
  } catch {
    return undefined;
  }
}

export function useCursorList<T, P extends Record<string, unknown>>({
  queryKey,
  params,
  fetchPage,
  enabled = true,
}: UseCursorListArgs<T, P>) {
  const [cursor, setCursor] = useState<string | undefined>(undefined);

  // Rule 2: reset the cursor the moment params change. Adjusting state during render
  // (React's recommended pattern) guarantees we never fetch new params + a stale
  // cursor in the same pass.
  const paramsKey = JSON.stringify(params);
  const [trackedKey, setTrackedKey] = useState(paramsKey);
  if (paramsKey !== trackedKey) {
    setTrackedKey(paramsKey);
    setCursor(undefined);
  }

  const query = useQuery({
    queryKey: [...queryKey, cursor ?? "first"],
    queryFn: () => fetchPage({ ...params, cursor }),
    enabled,
    // Keep the current rows visible while the next page loads.
    placeholderData: (prev) => prev,
  });

  const pagination = query.data?.pagination;

  return {
    rows: query.data?.rows ?? [],
    pagination,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isError: query.isError,
    error: query.error,
    hasNext: !!pagination?.next,
    hasPrev: !!pagination?.prev,
    next: () => setCursor(cursorOf(pagination?.next)),
    prev: () => setCursor(cursorOf(pagination?.prev)),
  };
}
